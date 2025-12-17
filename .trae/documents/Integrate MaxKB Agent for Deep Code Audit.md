I will implement the integration of the MaxKB Agent into the OpenScout system.

### Plan

1.  **Modify `server.py` (Backend)**
    *   Import `requests` and `StreamingResponse` from `fastapi.responses`.
    *   Implement helper functions to load specific user data:
        *   `load_tech_stack(username)`: Reads `data/raw_users/{username}/tech_stack.json`.
        *   `load_agent_b_context(username)`: Reads `data/raw_users/{username}/agent_b_context.json`.
        *   `load_radar_data(username)`: Existing logic, formatted as a string.
    *   Add a new API endpoint: `POST /api/analyze/{username}` (or GET with stream).
    *   This endpoint will:
        *   Gather the three data points.
        *   Construct a JSON payload for MaxKB with `inputs` mapping:
            *   `TechHunter` -> Tech Stack Data
            *   `CodeAuditor` -> Agent B Context
            *   `Six_Dimension` -> Radar Scores
        *   Send a POST request to the provided MaxKB URL (`http://localhost:8080/chat/api/019b2b1c-c20e-7241-afc1-9792bf8a1be1`).
        *   Stream the response back to the client.

2.  **Modify `OpenScout.htm` (Frontend)**
    *   Update the "Deep Audit" button (`#deepAuditBtn`) event listener.
    *   When clicked, clear the modal content and show a "Generating..." state.
    *   Initiate a `fetch` request to the new local API endpoint `/api/analyze/{username}`.
    *   Implement a stream reader (using `TextDecoder` and `ReadableStream`) to append the incoming text chunk-by-chunk to the Modal's body.
    *   Render the output as Markdown (if a markdown library is available, otherwise just text/HTML). *Note: The existing HTML has Tailwind `prose` class, suggesting Markdown support might be desired, but I will stick to streaming raw text/simple formatting first unless a library like `marked` is already included. Checking the HTML...*
    *   *Self-Correction*: I see `chart.js` and `tailwind` but no `marked.js` or `showdown.js` in the head. I will verify if I should add one or just display text. The user mentions "Markdown String Example" in previous prompts, so adding a lightweight Markdown renderer (e.g., via CDN) would be best for the report display.

### Configuration
*   **MaxKB URL**: `http://localhost:8080/chat/api/019b2b1c-c20e-7241-afc1-9792bf8a1be1`
*   **API Key**: `application-1ed17d275e94c89325484a52b336f5cf`

I will perform these edits now.