create or replace function public.socialscheduler_provider_edge_runtime(p_provider_key text)
returns jsonb
language plpgsql
security definer
set search_path = public, vault, pg_temp
as $$
declare
  v_result jsonb;
begin
  if current_user not in ('service_role', 'postgres') then
    raise exception 'not authorized';
  end if;

  select jsonb_build_object(
    'api_url', c.api_url,
    'api_key', s.decrypted_secret,
    'account_map', c.account_map,
    'worker_key', wk.decrypted_secret
  )
  into v_result
  from public.socialscheduler_provider_connections c
  join vault.decrypted_secrets s on s.id = c.secret_id
  cross join lateral (
    select decrypted_secret
    from vault.decrypted_secrets
    where name = 'socialscheduler_autopilot_cron_token'
    limit 1
  ) wk
  where c.provider_key = p_provider_key
    and c.enabled = true
  limit 1;

  return v_result;
end;
$$;

revoke all on function public.socialscheduler_provider_edge_runtime(text) from public, anon, authenticated;
grant execute on function public.socialscheduler_provider_edge_runtime(text) to service_role;

