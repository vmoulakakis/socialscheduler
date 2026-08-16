from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

BUFFER_ENDPOINT = "https://api.buffer.com"


class BufferAPIError(RuntimeError):
    pass


class BufferRateLimitError(BufferAPIError):
    def __init__(self, retry_after_seconds: int | None = None):
        self.retry_after_seconds = retry_after_seconds
        suffix = f"; Retry-After={retry_after_seconds}s" if retry_after_seconds is not None else ""
        super().__init__(f"Buffer HTTP 429 rate limited{suffix}")


@dataclass
class BufferClient:
    api_key: str
    endpoint: str = BUFFER_ENDPOINT
    max_retries: int = 1
    max_retry_after_seconds: int = 15
    request_timeout_seconds: int = 12

    @classmethod
    def from_env(cls) -> "BufferClient":
        key = os.getenv("BUFFER_API_KEY", "").strip()
        if not key:
            raise BufferAPIError("BUFFER_API_KEY is required")
        return cls(api_key=key)

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(
                self.endpoint,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "socialscheduler/3.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.request_timeout_seconds) as response:
                    body = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    retry_after = exc.headers.get("Retry-After")
                    retry_after_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
                    if retry_after_seconds and retry_after_seconds > self.max_retry_after_seconds:
                        raise BufferRateLimitError(retry_after_seconds) from exc
                    if attempt < self.max_retries:
                        delay = retry_after_seconds if retry_after_seconds is not None else 5
                        time.sleep(max(1, min(self.max_retry_after_seconds, delay)))
                        continue
                    raise BufferRateLimitError(retry_after_seconds) from exc
                detail = exc.read().decode("utf-8", errors="replace")
                raise BufferAPIError(f"Buffer HTTP {exc.code}: {detail[:500]}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < self.max_retries:
                    time.sleep(3)
                    continue
                raise BufferAPIError(
                    f"Buffer network/timeout error after {self.max_retries + 1} attempts: {exc}"
                ) from exc

            if body.get("errors"):
                raise BufferAPIError(f"Buffer GraphQL error: {body['errors']}")
            return body.get("data", {})
        raise BufferAPIError("Buffer request failed after retries")

    def account(self) -> dict[str, Any]:
        query = """
        query Account { account { id email organizations { id name } } }
        """
        return self.execute(query)["account"]

    def channels(self, organization_id: str) -> list[dict[str, Any]]:
        query = """
        query Channels($input: ChannelsInput!) {
          channels(input: $input) { id name service }
        }
        """
        return self.execute(query, {"input": {"organizationId": organization_id}})["channels"]

    def runtime_snapshot(self, organization_id: str) -> dict[str, Any]:
        """One Buffer request for org access, connected channels and active queue.

        Active queues are capped at 10 per channel on the current Free plan, so a
        single 100-node page safely covers our three connected channels.
        """
        query = """
        query RuntimeSnapshot($channelsInput: ChannelsInput!, $postsInput: PostsInput!, $first: Int) {
          account { id organizations { id name } }
          channels(input: $channelsInput) { id name service }
          posts(input: $postsInput, first: $first) {
            edges {
              node {
                id text channelId channelService status dueAt sentAt createdAt updatedAt
                shareMode schedulingType ideaId externalLink
                assets { id mimeType source thumbnail }
              }
            }
            pageInfo { endCursor hasNextPage }
          }
        }
        """
        variables = {
            "channelsInput": {"organizationId": organization_id},
            "postsInput": {
                "organizationId": organization_id,
                "filter": {"status": ["scheduled", "sending"]},
                "sort": [{"field": "dueAt", "direction": "asc"}],
            },
            "first": 100,
        }
        data = self.execute(query, variables)
        return {
            "account": data.get("account") or {},
            "channels": data.get("channels") or [],
            "posts": [edge.get("node") or {} for edge in (data.get("posts") or {}).get("edges", [])],
            "has_next_page": bool((data.get("posts") or {}).get("pageInfo", {}).get("hasNextPage")),
        }

    def _paginate(self, query: str, root: str, variables: dict[str, Any], page_size: int = 100) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        after = None
        while True:
            vars_page = dict(variables)
            vars_page.update({"first": page_size, "after": after})
            result = self.execute(query, vars_page)[root]
            nodes.extend(edge["node"] for edge in result.get("edges", []))
            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                return nodes
            after = page_info.get("endCursor")
            if not after:
                return nodes

    def posts(self, organization_id: str, statuses: Iterable[str]) -> list[dict[str, Any]]:
        query = """
        query Posts($input: PostsInput!, $first: Int, $after: String) {
          posts(input: $input, first: $first, after: $after) {
            edges {
              node {
                id text channelId channelService status dueAt sentAt createdAt updatedAt shareMode schedulingType ideaId externalLink
                assets { id mimeType source thumbnail }
              }
            }
            pageInfo { endCursor hasNextPage }
          }
        }
        """
        input_data = {
            "organizationId": organization_id,
            "filter": {"status": list(statuses)},
            "sort": [{"field": "dueAt", "direction": "asc"}, {"field": "createdAt", "direction": "desc"}],
        }
        return self._paginate(query, "posts", {"input": input_data})

    def sent_posts_with_metrics(self, organization_id: str, *, page_size: int = 100, max_pages: int = 5) -> list[dict[str, Any]]:
        query = """
        query SentPostsMetrics($input: PostsInput!, $first: Int, $after: String) {
          posts(input: $input, first: $first, after: $after) {
            edges {
              node {
                id text channelId channelService status dueAt sentAt externalLink
                metrics { type name value unit }
                metricsUpdatedAt
              }
            }
            pageInfo { endCursor hasNextPage }
          }
        }
        """
        input_data = {
            "organizationId": organization_id,
            "filter": {"status": ["sent"]},
            "sort": [{"field": "dueAt", "direction": "desc"}],
        }
        nodes: list[dict[str, Any]] = []
        after = None
        for _ in range(max(1, max_pages)):
            result = self.execute(query, {"input": input_data, "first": page_size, "after": after})["posts"]
            nodes.extend(edge.get("node") or {} for edge in result.get("edges", []))
            info = result.get("pageInfo", {})
            if not info.get("hasNextPage") or not info.get("endCursor"):
                break
            after = info.get("endCursor")
        return nodes

    def ideas(self, organization_id: str) -> list[dict[str, Any]]:
        query = """
        query Ideas($input: IdeasInput!, $first: Int, $after: String) {
          ideas(input: $input, first: $first, after: $after) {
            edges { node { id organizationId createdAt updatedAt content { title text date services media { url type } } } }
            pageInfo { endCursor hasNextPage }
          }
        }
        """
        return self._paginate(query, "ideas", {"input": {"organizationId": organization_id}})

    def create_idea(self, organization_id: str, content: dict[str, Any]) -> dict[str, Any]:
        query = """
        mutation CreateIdea($input: CreateIdeaInput!) {
          createIdea(input: $input) {
            ... on Idea { id organizationId content { title text date services } }
            ... on MutationError { message }
          }
        }
        """
        result = self.execute(query, {"input": {"organizationId": organization_id, "content": content}})["createIdea"]
        if result.get("message"):
            raise BufferAPIError(f"createIdea failed: {result['message']}")
        return result

    def create_post(self, input_data: dict[str, Any]) -> dict[str, Any]:
        if input_data.get("mode") in {"shareNow", "shareNext"}:
            raise BufferAPIError("Safety guard: shareNow/shareNext are forbidden")
        query = """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess { post { id text channelId status dueAt shareMode } }
            ... on MutationError { message }
          }
        }
        """
        result = self.execute(query, {"input": input_data})["createPost"]
        if result.get("message"):
            raise BufferAPIError(f"createPost failed: {result['message']}")
        return result["post"]

    def delete_post(self, post_id: str) -> str:
        query = """
        mutation DeletePost($input: DeletePostInput!) {
          deletePost(input: $input) {
            ... on DeletePostSuccess { id }
            ... on MutationError { message }
          }
        }
        """
        result = self.execute(query, {"input": {"id": post_id}})["deletePost"]
        if result.get("message"):
            raise BufferAPIError(f"deletePost failed: {result['message']}")
        return str(result.get("id") or post_id)
