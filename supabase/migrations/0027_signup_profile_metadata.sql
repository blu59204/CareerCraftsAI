-- Copy personal details submitted during signup into public.users.
-- Covers email-confirmation flows where the frontend cannot call /users/me yet.

CREATE OR REPLACE FUNCTION public.handle_new_supabase_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    INSERT INTO public.users (
        email,
        full_name,
        avatar_url,
        supabase_uid,
        phone,
        linkedin_url,
        headline
    )
    VALUES (
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
        COALESCE(NEW.raw_user_meta_data->>'avatar_url', NEW.raw_user_meta_data->>'picture'),
        NEW.id::text,
        NEW.raw_user_meta_data->>'phone',
        NEW.raw_user_meta_data->>'linkedin_url',
        NEW.raw_user_meta_data->>'headline'
    )
    ON CONFLICT (email) DO UPDATE
        SET supabase_uid = EXCLUDED.supabase_uid,
            full_name = COALESCE(public.users.full_name, EXCLUDED.full_name),
            avatar_url = COALESCE(public.users.avatar_url, EXCLUDED.avatar_url),
            phone = COALESCE(public.users.phone, EXCLUDED.phone),
            linkedin_url = COALESCE(public.users.linkedin_url, EXCLUDED.linkedin_url),
            headline = COALESCE(public.users.headline, EXCLUDED.headline);

    RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.handle_new_supabase_user() FROM PUBLIC;
