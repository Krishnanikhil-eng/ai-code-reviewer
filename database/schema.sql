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
