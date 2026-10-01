DO $$ BEGIN
  IF (SELECT count(*) FROM information_schema.columns WHERE table_schema='public'
      AND table_name='extension_tasks') <> 2 OR
      NOT (SELECT payload->>'preserved' = 'true' FROM public.extension_tasks LIMIT 1) THEN
    RAISE EXCEPTION 'Rollback changed task data or left approval columns';
  END IF;
END $$;
