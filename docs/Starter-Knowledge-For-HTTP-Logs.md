# Starter Knowledge For HTTP Logs

This document reflects platform-specific knowledge regarding HTTP logs;  their physical structure, what each field represents, any specific call outs for cross-domain knowledge, and other related topics.

Additionally, there will be a section called "Known Problems" which specifically addresses issues we are looking to address via this particular process.


## HTTP Logs

* log files, when provided in bulk, are NDJSON formatted
* logs, when streamed, be JSON formatted, with one log entry per injection

### Structure

This is an example, single, log entry (pretty printed)

```json
{
  "isotime": "2026-03-12T16:53:30-07:00",
  "log_type": "nginx",
  "server": "edge001.corleone",
  "xff": "47.202.140.153",
  "remoteaddr": "64.252.69.66",
  "remoteuser": "",
  "time": "12/Mar/2026:16:53:30 -0700",
  "http-host": "forms.ontraport.com",
  "request": "GET /v2.4/include/minify/?g=genjs-v3 HTTP/1.1",
  "http-status": "200",
  "sizesent": "50337",
  "http-referrer": "https://forms.ontraport.com/v2.4/include/formEditor/genlightbootstrap.php?uid=p2c268084f5&formType=modal&formGUID=OPF_b47df7bf-bede-a07f-c686-35e2d707f4a4&referer=https%3A%2F%2Faneliyahristova.com%2Fregister&formceptionID=formception-4df4cff7-251a-d132-ac1a-27c182198d1f&__opv=v1&lpid=71.0",
  "useragent": "Mozilla/5.0 (Linux; Android 16; SM-S908U1 Build/BP2A.250605.031.A3; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/145.0.7632.157 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/551.1.0.58.63;IABMV/1;]",
  "tts": "0.020",
  "http-orig-schema": "",
  "accountid": "",
  "session": "",
  "upstream": "172.25.80.3:443",
  "applempp": "FALSE",
  "trueip": "",
  "uuid": ""
}
```

### Field Definitions

In general, most fields will have values.  In some cases, they will not, but they should always be included, even when empty.

* isotime - ISO timestamp for when the even was logged
* log_type - string representation of the logging service; usually nginx
* server - the server that handled the request
* xff - the X-Forwarded-For header
* remoteaddr - this is the REMOTEADDR HTTP header;  this is can represent internal IPs, or public IPs
* remoteuser - this is the REMOTEUSER HTTP header;  it is usually blank
* time - another timestamp, representing the time of the request;  I can't remember the format, but it's standard
* http-host - this is the HOST HTTP header
* request - this is the non-domain portion of the request, including query string
* http-status - this is the HTTP response code (200, 302, 404, etc)
* sizesent - this is the number of bytes sent to the client in the response, in totality
* http-referrer - this is the "referrer";  this may or may not have data
* useragent - this is the User-Agent string;  this may or may not have data
* tts - this is "time to serve" in seconds;  this represents the time from request received, to connection closed
* http-orig-schema - Honestly, i can't remember, but I think it's usually blank
* accountid - this is the account id associated with the request;  this currently only functions properly when api.ontraport.com is the "http-host"
* session - this represents the custom session information;  it is usually blank, due to bugs
* upstream - this represents where the receiving server sent the request internally
* applempp - this represents whether or not the server believes this is an Apple MPP based (ie, anonymized) request (email opens usually)
* trueip - this represents the "true client ip", as algorithmically extrapolated.
* uuid - this is a UUID applied to every request

It is worth noting that, due to bugs and other conditions, some fields are not filled out (accountid, session, trueip, uuid).  


## Platform Specific Knowledge

* PHP requests (those ending in .php, sans query string) - these request are only valid with specific HTTP HOST headers;  when PHP requests are made against other endpoints, it is almost certainly abusive/scanner traffic
  * app.ontraport.com - the main application domain
  * api.ontraport.com - the API domain
  * optassets.ontraport.com - the static assets endpoint;  note, this does also include dynamic content
  * forms.ontraport.com - the form endpoint
* HTTP 679 response code - this represents that a request should have been serviced normally, but resulted in a 404 instead;  these response codes indicate internal bugs
* HTTP 429 response code - these are rate limiting responses, but there are two versions;  there is not a way to identify which rate limit resulted in the 429 response code
  * requests per minute - this is the normal/most common use-case
  * concurrent requests - we limit concurrent requests, meaning that only some ammount of requests can be operating over long durations
* We host 10's of thousands of domains, and 100's of thousands of full URLs for our clients.
  * Some clients may have one domain, and a few pages
  * Many clients have dozens, or more domains, and hundreds to thousands of pages

## Known Problems

We are looking to resolve several issues via HTTP log processing:

* form fillout bot detection - machine generated requests specifically to forms.ontraport.com
* abusive behavior - scanners, DDoS, etc
* account id based usage
* datacenter/hosted IPs (DCH) - there are many endpoints that are intended for human usage, exclusively.  any DCH IPs accessing these HTTP HOSTs are suspect
  * forms.ontraport.com - high priority
  * app.ontraport.com - high priority
  * optassets.ontraport.com - low priority




