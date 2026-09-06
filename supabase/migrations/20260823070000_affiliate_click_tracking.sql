create table if not exists public.socialscheduler_affiliate_clicks (
  id bigint generated always as identity primary key,
  clicked_at timestamptz not null default now(),
  seed_key text not null,
  platform text not null default 'unknown',
  campaign text,
  user_agent text,
  destination_host text not null
);

alter table public.socialscheduler_affiliate_clicks enable row level security;

create index if not exists socialscheduler_affiliate_clicks_seed_time_idx
  on public.socialscheduler_affiliate_clicks (seed_key, clicked_at desc);

create index if not exists socialscheduler_affiliate_clicks_campaign_time_idx
  on public.socialscheduler_affiliate_clicks (campaign, clicked_at desc)
  where campaign is not null;

create or replace function public.socialscheduler_track_affiliate_click(
  p_seed_key text,
  p_platform text default 'unknown',
  p_campaign text default null,
  p_user_agent text default null
) returns text
language plpgsql
security definer
set search_path = public, ops, pg_temp
as $$
declare
  v_destination text;
  v_host text;
  v_platform text;
begin
  v_platform := case
    when lower(coalesce(p_platform, '')) in ('facebook','instagram','tiktok','linkedin')
      then lower(p_platform)
    else 'unknown'
  end;

  select tracking_url
    into v_destination
  from ops.pain_solver_campaign_seeds
  where seed_key = p_seed_key
    and status = 'active'
    and tracking_url is not null
    and (season_start is null or current_date >= season_start)
    and (season_end is null or current_date <= season_end)
  limit 1;

  if v_destination is null or v_destination !~ '^https://go\\.linkwi\\.se/' then
    return null;
  end if;

  v_host := split_part(split_part(v_destination, '://', 2), '/', 1);

  insert into public.socialscheduler_affiliate_clicks
    (seed_key, platform, campaign, user_agent, destination_host)
  values
    (p_seed_key, v_platform, nullif(left(coalesce(p_campaign, ''), 120), ''),
     nullif(left(coalesce(p_user_agent, ''), 500), ''), v_host);

  return v_destination;
end;
$$;

revoke all on table public.socialscheduler_affiliate_clicks from anon, authenticated;
revoke all on function public.socialscheduler_track_affiliate_click(text,text,text,text) from public, anon, authenticated;
grant execute on function public.socialscheduler_track_affiliate_click(text,text,text,text) to service_role;

comment on table public.socialscheduler_affiliate_clicks is
  'Privacy-minimized click log for SocialScheduler affiliate redirects; no IP address is stored.';

