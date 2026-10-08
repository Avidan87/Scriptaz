# Scriptaz public-release checklist

## Must be complete before changing repository visibility

- [ ] Rotate any credentials that may ever have been committed; scan current files and Git history for keys, tokens, and local paths.
- [ ] Add a real `LICENSE` for the Scriptaz source code.
- [ ] Remove proprietary Bible PDFs and translation JSON from Git tracking unless written redistribution permission is verified.
- [ ] Because tracked files remain reachable through Git history, either publish a fresh clean source repository or perform a reviewed history rewrite before making an existing private repository public.
- [ ] Record the source, licence, required notice, and redistribution approval for KJV, ESV, NKJV, and NLT separately.
- [ ] Build the data pack only from approved translations and attach it to a release rather than committing it to Git.
- [ ] Set the release URL and SHA-256 in the distribution configuration.
- [ ] Confirm the README never tells users to commit AWS credentials.
- [ ] Test a clean install without AI and then a deliberately configured AI setup. This is intentionally deferred until the release groundwork is reviewed.

## Existing repository content needing a decision

The repository currently tracks Bible PDFs and canonical translation JSON files. Those files are not secrets, but public redistribution rights are not automatically implied by local possession. Keep them private until the licence audit is complete; the release pack should follow the same rule.
