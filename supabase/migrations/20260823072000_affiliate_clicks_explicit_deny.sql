create policy socialscheduler_affiliate_clicks_deny_client_access
on public.socialscheduler_affiliate_clicks
as restrictive
for all
to anon, authenticated
using (false)
with check (false);

