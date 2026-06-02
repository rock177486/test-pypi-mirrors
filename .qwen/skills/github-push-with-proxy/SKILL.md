---
name: github-push-with-proxy
description: Push a local git repository to GitHub when direct HTTPS/SSH connections fail (common in China due to network restrictions)
source: auto-skill
extracted_at: '2026-06-01T03:18:09.183Z'
---

# Pushing to GitHub with Proxy (China Network Environment)

## When to Use

This skill applies when:
- You need to push a local git repo to GitHub
- Direct HTTPS connections to GitHub time out or fail
- SSH connections fail due to missing keys
- You're working in a network environment where GitHub is blocked or slow (common in mainland China)

## Procedure

### 1. Initial Setup Check

First verify the current state:

```bash
git status
git log --oneline -n 3
gh auth status  # Check if GitHub CLI is available
```

If no commits exist yet, create an initial commit:

```bash
git config user.name "your-username"
git config user.email "your-email@example.com"
git add -A
git commit -m "Initial commit"
```

### 2. Try Direct Connection (HTTPS)

Attempt a standard HTTPS push:

```bash
git remote add origin https://github.com/username/repo.git
git push -u origin master
```

**Expected failure in restricted networks:** Connection timeout after 21+ seconds with error:
```
fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443 after 21061 ms: Could not connect to server
```

### 3. Try SSH (If HTTPS Fails)

Switch to SSH and attempt push:

```bash
git remote set-url origin git@github.com:username/repo.git
git push -u origin master
```

**Expected failures:**
- SSH host key verification prompt (timeout waiting for user input)
- Permission denied if no SSH keys configured:
  ```
  git@github.com: Permission denied (publickey).
  fatal: Could not read from remote repository.
  ```

If SSH host key issue, add GitHub's key to known_hosts:

```bash
echo "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" >> ~/.ssh/known_hosts
```

### 4. Configure Proxy for Push

When direct connections fail, ask the user for their proxy address (common formats):
- `http://127.0.0.1:7890` (Clash default)
- `http://127.0.0.1:1080` (common SOCKS/HTTP proxy)
- `http://127.0.0.1:10809` (V2Ray default)

**One-time push with proxy:**

```bash
git remote set-url origin https://github.com/username/repo.git
git -c http.proxy=http://proxy:port -c https.proxy=http://proxy:port push -u origin master
```

This uses the `-c` flag to pass proxy configuration for this single command only.

**Persist proxy configuration for the repository:**

```bash
git config http.proxy http://proxy:port
git config https.proxy http://proxy:port
```

This saves the proxy settings in the repository's local `.git/config`, so future `git push` commands will automatically use the proxy.

### 5. Verify Success

After successful push, you should see:

```
Enumerating objects: 9, done.
Counting objects: 100% (9/9), done.
...
To https://github.com/username/repo.git
 * [new branch]      master -> master
branch 'master' set up to track 'origin/master'.
```

## Key Learnings

1. **HTTPS often times out** in restricted networks before SSH fails, so try HTTPS first to diagnose network issues
2. **Use `-c` flag for one-time proxy config** when testing, then persist with `git config` once confirmed working
3. **Per-repository proxy config** (not global) is safer — it only affects this specific repo
4. **Proxy format matters:** Use `http://` prefix even for SOCKS proxies when configuring git
5. **Authentication flows** may pop up in browser for HTTPS pushes — ensure the user can interact with the browser

## Troubleshooting

### Browser authentication timeout
If `info: please complete authentication in your browser...` appears but times out, the user needs to:
- Check that a browser window opened
- Complete the GitHub OAuth flow
- Return to the terminal

### Proxy not working
- Verify the proxy is running and accessible: `curl -x http://proxy:port https://github.com`
- Try different proxy ports if the user's proxy tool uses non-standard ports
- Check if the proxy requires authentication (rare for local proxies)

### Switch between proxy and direct connection
To remove proxy config for this repo:
```bash
git config --unset http.proxy
git config --unset https.proxy
```

## Example Session

```bash
# Initial state: new repo, no commits
git config user.name "rock177486"
git config user.email "177486@qq.com"
git add -A
git commit -m "Initial commit"

# Try HTTPS (fails with timeout)
git remote add origin https://github.com/rock177486/test-pypi-mirrors.git
git push -u origin master
# fatal: unable to access... Failed to connect to github.com port 443 after 21061 ms

# Try SSH (fails - no keys)
git remote set-url origin git@github.com:rock177486/test-pypi-mirrors.git
git push -u origin master
# git@github.com: Permission denied (publickey)

# Add GitHub SSH key to known_hosts
echo "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl" >> ~/.ssh/known_hosts

# Back to HTTPS with proxy
git remote set-url origin https://github.com/rock177486/test-pypi-mirrors.git
git -c http.proxy=http://10.217.24.53:7890 -c https.proxy=http://10.217.24.53:7890 push -u origin master
# Success!

# Persist proxy for future use
git config http.proxy http://10.217.24.53:7890
git config https.proxy http://10.217.24.53:7890
```
