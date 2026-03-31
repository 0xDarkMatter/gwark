# Gmail Query Syntax Reference

Full operator reference for `gwark email search --query "..."` and `gwark email senders --query "..."`.

## Sender/Recipient

| Operator | Example | Notes |
|----------|---------|-------|
| `from:` | `from:alice@example.com` | Exact sender |
| `from:` | `from:alice` | Partial match (name or email) |
| `from:@` | `from:@example.com` | Domain match |
| `to:` | `to:bob@example.com` | Recipient |
| `cc:` | `cc:manager@example.com` | CC field |
| `bcc:` | `bcc:secret@example.com` | BCC field |

## Content

| Operator | Example | Notes |
|----------|---------|-------|
| bare words | `project update` | Full-text (subject + body) |
| `"quoted"` | `"exact phrase"` | Exact phrase match |
| `subject:` | `subject:invoice` | Subject only |
| `subject:` | `subject:"Q4 Report"` | Subject exact phrase |

## Dates

| Operator | Example | Notes |
|----------|---------|-------|
| `after:` | `after:2025/01/01` | After date (YYYY/MM/DD) |
| `before:` | `before:2025/06/01` | Before date |
| `older_than:` | `older_than:7d` | Relative: d(ays), m(onths), y(ears) |
| `newer_than:` | `newer_than:2w` | Relative: w(eeks) also works |

## Attachments & Size

| Operator | Example | Notes |
|----------|---------|-------|
| `has:attachment` | `has:attachment` | Has any attachment |
| `filename:` | `filename:pdf` | Attachment type |
| `filename:` | `filename:report.xlsx` | Specific filename |
| `larger:` | `larger:5M` | Size > 5MB (K, M units) |
| `smaller:` | `smaller:100K` | Size < 100KB |

## Status & Labels

| Operator | Example | Notes |
|----------|---------|-------|
| `is:unread` | `is:unread` | Unread messages |
| `is:read` | `is:read` | Read messages |
| `is:starred` | `is:starred` | Starred |
| `is:important` | `is:important` | Marked important |
| `label:` | `label:INBOX` | Gmail label |
| `label:` | `label:work/projects` | Nested label |
| `in:` | `in:sent` | In sent folder |
| `in:` | `in:trash` | In trash |
| `in:` | `in:anywhere` | All mail including trash/spam |
| `category:` | `category:updates` | Gmail category tab |

## Boolean Logic

| Operator | Example | Notes |
|----------|---------|-------|
| space | `from:alice subject:report` | AND (implicit) |
| `OR` | `from:alice OR from:bob` | OR (must be uppercase) |
| `-` | `-from:noreply@` | NOT (exclude) |
| `()` | `(from:alice OR from:bob) subject:report` | Grouping |

## Complex Examples

```bash
# Unread emails with attachments from last week
gwark email search --query "is:unread has:attachment newer_than:7d"

# Emails from two domains, excluding newsletters
gwark email search --query "(from:@client1.com OR from:@client2.com) -from:newsletter@"

# Large emails in sent folder
gwark email search --query "in:sent larger:10M"

# Starred emails about invoices from this year
gwark email search --query "is:starred subject:invoice after:2025/01/01"

# Find all unique senders from multiple domains
gwark email senders --query "(from:@partner1.com OR from:@partner2.com OR from:@partner3.com)"
```

## Gotchas

- `OR` must be uppercase. `or` is treated as a search term.
- `-` (NOT) must have no space: `-from:spam@` not `- from:spam@`.
- `from:` matches display name AND email. `from:John` finds "John Smith <js@example.com>".
- Dates use forward slashes: `after:2025/01/01` not `after:2025-01-01`.
- `in:anywhere` searches trash and spam too. Default search excludes them.
