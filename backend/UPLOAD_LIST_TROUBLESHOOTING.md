# Uploaded files missing from the list

Mapping and Uploaded Files read the same `uploads` database table. Mapping calls
`/uploads/job/{job_id}`; the history page lists all uploads for the signed-in
company. Upload metadata is committed when an upload succeeds. This listing
does not depend on Redis or a separate indexing job.

Two code issues could hide existing uploads:

- The frontend requested `/uploads`, but only `/uploads/` was registered. This
  required a redirect. A proxy that strips `/api` without rewriting redirect
  locations can send the browser to a frontend HTML page instead of the API.
  The Railway Nginx template already rewrites redirects, but the root Compose
  proxy does not. The deployed proxy configuration has not been verified.
- Both request failures and unexpected response shapes were treated as an empty
  list, displaying “No files uploaded yet” with zero counters.

The fix registers both backend paths directly and requests `/uploads/` in the
frontend. Errors now appear beside the table with Refresh guidance. Failed
refreshes retain the last loaded list; initial failures show unavailable counts.
Loading the list no longer waits for the jobs and processors dropdown requests.
Successful empty responses still display the normal empty state.

## Deployment and checks

1. Deploy both the API and frontend changes, then hard-refresh the uploads page
   so the browser loads the new JavaScript. No schema migration or re-upload is
   needed for this fix.
2. While signed in, open browser developer tools → Network and press Refresh
   above Uploaded Files. `/api/uploads/` should return 200 with a JSON array,
   with no redirect. A known filename should be in the response.
3. If the response is HTML, verify that `/api/` is routed to the backend and that
   `RECON_API_URL` uses the correct same-origin API prefix. Check the response
   URL for a missing `/api` prefix. Do not paste session cookies into tickets.
4. For 401, sign in again. For 403, check account/subscription permissions. For
   5xx, inspect the API logs using the response's `X-Request-Id`, if present.
5. For a real empty array, compare with `/api/uploads/job/<job-id>` using the
   same signed-in session. Confirm the API services point to the same database
   and the files belong to that user's company. Company filtering is intentional.
6. If JSON contains the expected records but the table is empty, inspect the
   browser console for rendering errors and confirm the deployed frontend
   includes `uploadsListMessage` and the updated `js/uploads.js`.

Existing mapping access is evidence that metadata and stored files are present;
do not rebuild indexes or delete/re-upload working files without further evidence.
The live Railway environment was not accessed during this fix.

Regression checks: `python -m unittest discover -s tests -v` from `backend`,
and `node --test frontend/tests/uploads.test.cjs` from the repository root.
