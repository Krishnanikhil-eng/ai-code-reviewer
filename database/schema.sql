-- Schema for AI Code Reviewer Feedback Loop

CREATE TABLE IF NOT EXISTS ai_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    github_comment_id INTEGER UNIQUE, -- ID assigned by GitHub API
    repo_full_name TEXT NOT NULL,
    pr_number INTEGER NOT NULL,
    file_path TEXT,
    code_snippet TEXT,
    comment_text TEXT,
    suggested_fix TEXT,
    score INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gh_comment_id ON ai_comments(github_comment_id);

CREATE TABLE IF NOT EXISTS repo_settings (
    repo_full_name TEXT PRIMARY KEY,
    strictness INTEGER DEFAULT 3,
    review_mode TEXT DEFAULT 'standard',
    custom_prompt TEXT DEFAULT '',
    retrieval_depth INTEGER DEFAULT 3
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_role TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
