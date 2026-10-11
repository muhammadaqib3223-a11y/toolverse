-- Toolverse: profile photos for saved CVs (Phase 6C). Run once in the Supabase SQL Editor,
-- after 20261015_cvs.sql.
--
-- How photos work:
--   * The browser shrinks the photo (max 512 px, JPEG) before sending it. The app server checks
--     it, re-saves it as a clean JPEG (this also removes hidden data such as GPS location) and
--     uploads it to the PRIVATE bucket `cv-photos` as  <user id>/<cv id>.jpg
--   * Only the owner can read, add, replace or delete files in their own folder (policies below).
--     The bucket is not public: there is no public link to anyone's photo.
--   * cvs.photo_path remembers which file belongs to a CV. Deleting a CV deletes its photo too
--     (done by the app).
--   * Guests' photos never reach Supabase: they stay in the browser with the guest CV.

-- 1. Which photo belongs to a CV (null = no photo).
alter table public.cvs
  add column photo_path text
  check (photo_path is null or photo_path ~ '^[0-9a-f-]{36}/[0-9a-f-]{36}\.jpg$');
grant update (photo_path) on public.cvs to authenticated;

-- 2. A private bucket: JPEG only, at most 300 KB per file.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('cv-photos', 'cv-photos', false, 307200, array['image/jpeg'])
on conflict (id) do update
  set public = false, file_size_limit = 307200, allowed_mime_types = array['image/jpeg'];

-- 3. Each user may only touch files inside the folder named after their own user id.
create policy "Users can read their own CV photos"
  on storage.objects for select to authenticated
  using (bucket_id = 'cv-photos' and (storage.foldername(name))[1] = (select auth.uid()::text));

create policy "Users can upload their own CV photos"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'cv-photos' and (storage.foldername(name))[1] = (select auth.uid()::text));

create policy "Users can replace their own CV photos"
  on storage.objects for update to authenticated
  using (bucket_id = 'cv-photos' and (storage.foldername(name))[1] = (select auth.uid()::text))
  with check (bucket_id = 'cv-photos' and (storage.foldername(name))[1] = (select auth.uid()::text));

create policy "Users can delete their own CV photos"
  on storage.objects for delete to authenticated
  using (bucket_id = 'cv-photos' and (storage.foldername(name))[1] = (select auth.uid()::text));
