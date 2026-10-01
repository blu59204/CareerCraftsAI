INSERT INTO job_search_defaults VALUES('00000000-0000-0000-0000-000000000001','resume','00000000-0000-0000-0000-000000000002');
INSERT INTO github_profiles(user_id,mode,login,data) VALUES('00000000-0000-0000-0000-000000000001','public_url','test','{"skills":[],"top_repos":[],"suggested_projects":[]}');
INSERT INTO job_source_health(source_id) VALUES('recorded:test');
INSERT INTO job_catalog(job_id,url,title,company,posted_at,data)
 SELECT n::text,'https://jobs.example/'||n,CASE WHEN n%10=0 THEN 'Python Engineer' ELSE 'Other Role' END,'Company',now(),'{}' FROM generate_series(1,100000) n;
INSERT INTO job_source_occurrences(job_id,source_id) SELECT job_id,'recorded:test' FROM job_catalog;
INSERT INTO job_match_embeddings(user_id,job_id,provider,dimensions,content_hash,embedding)
 SELECT '00000000-0000-0000-0000-000000000001',n::text,'recorded',768,'hash',('['||array_to_string(ARRAY[1]||array_fill(0,ARRAY[767]),',')||']')::vector FROM generate_series(1,1000) n;
ANALYZE job_catalog; ANALYZE job_source_occurrences; ANALYZE job_match_embeddings;
EXPLAIN (ANALYZE,BUFFERS) SELECT job_id FROM job_catalog WHERE lower(title) LIKE '%python%' AND posted_at > now()-interval '30 days' LIMIT 100;
EXPLAIN (ANALYZE,BUFFERS) SELECT job_id FROM job_match_embeddings WHERE user_id='00000000-0000-0000-0000-000000000001' AND dimensions=768 ORDER BY embedding::vector(768) <=> ('['||array_to_string(ARRAY[1]||array_fill(0,ARRAY[767]),',')||']')::vector(768) LIMIT 10;
DO $$ BEGIN
 IF (SELECT count(*) FROM pg_class WHERE relname IN ('job_search_defaults','github_profiles','job_catalog','job_source_occurrences','job_match_embeddings','job_source_health') AND relrowsecurity)<>6 THEN RAISE EXCEPTION 'RLS missing'; END IF;
 IF has_table_privilege('authenticated','public.github_profiles','SELECT') OR has_table_privilege('anon','public.job_catalog','SELECT') THEN RAISE EXCEPTION 'Unscoped data exposed'; END IF;
 IF (SELECT count(*) FROM pg_indexes WHERE indexname IN ('b_job_embeddings_768','b_job_embeddings_1024','b_job_embeddings_1536'))<>3 THEN RAISE EXCEPTION 'Vector indexes missing'; END IF;
END $$;
