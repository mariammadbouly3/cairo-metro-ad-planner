-- 08: contact details for booking requests sent from the website.
-- The app runs these automatically when it starts (writes.ensure_schema), so you don't have to.
-- Safe to run again: IF NOT EXISTS skips columns that are already there.
SET search_path TO cairo_metro;

ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS contact_name  VARCHAR(120);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(40);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS contact_email VARCHAR(160);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS notes         TEXT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS created_at    TIMESTAMPTZ DEFAULT now();

-- Requests waiting for review, newest first
SELECT c.campaign_id, a.company_name, c.contact_name, c.contact_phone, c.contact_email,
       COUNT(b.*) AS spaces, SUM(b.price_egp) AS value_egp, MIN(b.created_at) AS sent_at
FROM campaigns c
JOIN advertisers a USING (advertiser_id)
JOIN bookings b USING (campaign_id)
WHERE b.status = 'pending'
GROUP BY 1, 2, 3, 4, 5
ORDER BY sent_at DESC;
