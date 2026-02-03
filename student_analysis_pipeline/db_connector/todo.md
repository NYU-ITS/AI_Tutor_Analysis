# Project Status and Future Plan

## Phase 1: Data Connector (DONE)

1. Found where the data is stored in the Open WebUI database.
2. Built the connection to read Users, Groups, and Chats.
3. Made an API to pull the data easily.
4. Added settings to filter by Group name, Model name, and Dates.
5. Fixed the file saving: all chats for one student now go into one file.
6. Set up automatic folders to save the exported files.
7. Moved passwords and keys to a secure .env file.
8. Tested everything and confirmed it works with the server tunnel.

## Phase 2: Data Storage for Persistence and Traceability (Future)

To scale analysis, exported data can be synchronized to a tracking table to prevent duplication and monitor processing status.

### raw_conversations Table Schema

| Column | Type | Description |
|---|---|---|
| id | INT | Primary Key (AI) |
| openwebui_conversation_id | VARCHAR(255) | Unique ID (Prevents duplicates) |
| user_id | VARCHAR(255) | Student identification (Email) |
| model_name | VARCHAR(255) | Target homework model |
| group_name | VARCHAR(255) | Student cohort/group |
| conversation_history | JSON | Full conversation record |
| fetched_at | TIMESTAMP | Date of extraction |
| is_processed | BOOLEAN | Status indicator for analysis pipeline |

### Key Benefits

- Unique ID Check: The openwebui_conversation_id ensures that multiple exports from the source do not create duplicate records in the analysis database.
- Parallelization: The is_processed flag allows multiple pipeline workers to identify new data safely.
