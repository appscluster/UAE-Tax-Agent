# Incident note

This note says who to tell and which volume to freeze. It does not describe an investigation that already happened.

If the volume key leaks, or someone suspects a document left the machine:

1. Stop the stack: `docker compose stop`.
2. Leave the `tenant` and `backup` volumes in place. Do not delete them until the operator has a copy.
3. Tell the person who holds the customer relationship and, where personal data is involved, the person who owns the UAE PDPL question. The public starting points are the UAE data-protection overview and Federal Decree-Law No. 45 of 2021, Articles 22 and 23. This note is not that legal advice.
4. Rotate `TENANT_VOLUME_KEY` only after the volumes are copied. A new key cannot read the old database.
5. Record the time, the run id, and whether `RESIDENCY_VERIFIED` was true. Do not paste document bodies into chat or email.

A localhost OmniRoute URL is not evidence that processing stayed in the UAE.
