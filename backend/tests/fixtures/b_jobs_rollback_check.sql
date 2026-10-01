DO $$ BEGIN
 IF to_regclass('public.job_catalog') IS NOT NULL OR to_regclass('public.github_profiles') IS NOT NULL OR to_regclass('public.job_search_defaults') IS NOT NULL THEN RAISE EXCEPTION 'Rollback incomplete'; END IF;
 IF (SELECT notes FROM public.job_applications LIMIT 1)<>'preserved' THEN RAISE EXCEPTION 'Existing data changed'; END IF;
END $$;
