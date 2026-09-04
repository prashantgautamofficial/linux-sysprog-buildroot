# AESD Assignment 5 Part 2 — Buildroot Embedded Socket Server Procedure

**Repos involved:**
- Buildroot / submission repo: `https://github.com/prashantgautamofficial/aeld-assignment-5`
- Buildroot content source: `https://github.com/cu-ecen-aeld/assignment-4-prashantgautamofficial`
- Server application repo: `https://github.com/cu-ecen-aeld/aeld-assignment-3-and-later`

---

## Step 1 — Bring Buildroot content into the new repo

Run on the local `aeld-assignment-4` working copy:

```bash
cd ~/Documents/aeld-assignment-4

# rename existing origin
git remote rename origin assignment-4-remote

# pull in the assignment 5 base content
git remote add buildroot-assignments-base https://github.com/cu-ecen-aeld/buildroot-assignments-base.git
git fetch buildroot-assignments-base
git merge buildroot-assignments-base/assignment5

# sync buildroot submodule and any others
git submodule update --init --recursive

# point origin at the new empty assignment-5 repo
git remote add origin https://github.com/prashantgautamofficial/aeld-assignment-5.git
git push origin main
```

**If the push is rejected as non-fast-forward** (new repo already has a commit, e.g. an
auto-generated README from GitHub Classroom):

```bash
git remote -v                     # confirm origin points to aeld-assignment-5
git pull origin main --allow-unrelated-histories --no-rebase
```

This opens an editor for a merge commit message — save and close it (`nano`:
`Ctrl+O`, `Enter`, `Ctrl+X`; `vim`: `:wq`).

Resolve any conflicts (e.g. `README.md`):

```bash
git status
# edit conflicting file(s) to keep the desired content
git add README.md
git commit
```

Then push:

```bash
git push origin main
```

**Notes:**
- If `git remote add origin ...` fails with `remote origin already exists`, remove and
  re-add it:
  ```bash
  git remote remove origin
  git remote add origin https://github.com/prashantgautamofficial/aeld-assignment-5.git
  ```
- Recommended: re-clone fresh into a clean local folder once pushed:
  ```bash
  cd ~/Documents
  rm -rf aeld-assignment-5
  git clone --recurse-submodules https://github.com/prashantgautamofficial/aeld-assignment-5.git
  cd aeld-assignment-5
  ```

---

## Step 2 — Verify `aesdsocket-start-stop` is in place

```bash
cd ~/Documents/aeld-assignment-3-and-later
git pull origin main
ls -l server/
cat server/aesdsocket-start-stop
```

## Step 2.1 — Write `aesdsocket-start-stop` with following code

```bash
#!/bin/sh

case "$1" in
    start)
        echo "Starting aesdsocket"
        start-stop-daemon -S -n aesdsocket -a /usr/bin/aesdsocket -- -d
        ;;
    stop)
        echo "Stopping aesdsocket"
        start-stop-daemon -K -n aesdsocket -s TERM
        ;;
    *)
        echo "Usage: $0 {start|stop}"
        exit 1
        ;;
esac

exit 0
```

```bash
chmod +x server/aesdsocket-start-stop
```

Confirm it's present, executable, and uses `start-stop-daemon -S`/`-K` with `-d`
daemon mode and SIGTERM handling on stop.

Note the latest commit hash on `main` (needed for `AESD_ASSIGNMENTS_VERSION`):

```bash
git log --oneline -3
```

```bash
git log -1 --format="%H"
```
```bash
555eede434d62471b030370f1e037f8bc3e46655
```

## Step 2.2 — Write `Makefile` with following code

```bash
touch server/Makefile
```

```bash
nano server/Makefile
```

```bash
CC := $(CROSS_COMPILE)gcc
CFLAGS ?= -Wall -Wextra -g -O0
TARGET := aesdsocket
SRCS := aesdsocket.c
OBJS := $(SRCS:.c=.o)

.PHONY: all default clean

all: $(TARGET)
default: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $(TARGET) $(OBJS) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(TARGET) $(OBJS)
```

Quick dry-run test — this proves it without needing the actual cross-toolchain installed:

```bash
make clean
make CROSS_COMPILE=aarch64-none-linux-gnu- --dry-run
```

Check the printed compile line. You want to see:

```bash
aarch64-none-linux-gnu-gcc -Wall -Wextra -g -O0 -c aesdsocket.c -o aesdsocket.o
```

## Step 2.3 — Check the `aesdsocket.c` code

```bash
nano ~/Documents/aeld-assignment-3-and-later/server/aesdsocket.c
```

```c
/*
 * aesdsocket.c
 *
 * AESD Assignment 5 Part 1 - stream socket server.
 *
 * Opens a stream socket on port 9000, accepts connections, receives
 * newline-delimited data packets, appends each completed packet to
 * /var/tmp/aesdsocketdata, and returns the full contents of that file
 * back to the client after each packet is received.
 *
 * Supports:
 *   - Logging via syslog (LOG_USER facility)
 *   - Graceful shutdown on SIGINT/SIGTERM (closes sockets, removes data file)
 *   - "-d" argument to run as a daemon (fork occurs only after successful bind)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <fcntl.h>
#include <syslog.h>
#include <stdbool.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>

#define PORT            "9000"
#define DATA_FILE       "/var/tmp/aesdsocketdata"
#define BACKLOG         10
#define RECV_CHUNK_SIZE 1024

/* Globals needed by the signal handler for graceful cleanup */
static volatile sig_atomic_t g_shutdown_requested = 0;
static int g_listen_fd = -1;
static int g_client_fd = -1;

static void signal_handler(int signo)
{
    (void)signo;
    g_shutdown_requested = 1;

    /*
     * Shut down whichever sockets are currently open so any blocking
     * accept()/recv() call unblocks with an error we can check for.
     * Only async-signal-safe calls are used here.
     */
    if (g_client_fd != -1)
    {
        shutdown(g_client_fd, SHUT_RDWR);
    }
    if (g_listen_fd != -1)
    {
        shutdown(g_listen_fd, SHUT_RDWR);
    }
}

static int setup_signal_handlers(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = signal_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = 0; /* no SA_RESTART: we want blocking calls to return EINTR */

    if (sigaction(SIGINT, &sa, NULL) == -1)
    {
        syslog(LOG_ERR, "sigaction(SIGINT) failed: %s", strerror(errno));
        return -1;
    }
    if (sigaction(SIGTERM, &sa, NULL) == -1)
    {
        syslog(LOG_ERR, "sigaction(SIGTERM) failed: %s", strerror(errno));
        return -1;
    }
    return 0;
}

/*
 * Creates, binds, and starts listening on a stream socket for PORT.
 * Returns the listening fd, or -1 on any failure.
 */
static int create_and_bind_listen_socket(void)
{
    struct addrinfo hints, *res, *rp;
    int sockfd = -1;
    int yes = 1;
    int rv;

    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    hints.ai_flags = AI_PASSIVE;

    rv = getaddrinfo(NULL, PORT, &hints, &res);
    if (rv != 0)
    {
        syslog(LOG_ERR, "getaddrinfo failed: %s", gai_strerror(rv));
        return -1;
    }

    for (rp = res; rp != NULL; rp = rp->ai_next)
    {
        sockfd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (sockfd == -1)
        {
            continue;
        }

        if (setsockopt(sockfd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) == -1)
        {
            syslog(LOG_ERR, "setsockopt failed: %s", strerror(errno));
            close(sockfd);
            sockfd = -1;
            continue;
        }

        if (bind(sockfd, rp->ai_addr, rp->ai_addrlen) == -1)
        {
            close(sockfd);
            sockfd = -1;
            continue;
        }

        break; /* success */
    }

    freeaddrinfo(res);

    if (sockfd == -1)
    {
        syslog(LOG_ERR, "Failed to bind socket on port %s: %s", PORT, strerror(errno));
        return -1;
    }

    if (listen(sockfd, BACKLOG) == -1)
    {
        syslog(LOG_ERR, "listen failed: %s", strerror(errno));
        close(sockfd);
        return -1;
    }

    return sockfd;
}

/*
 * Receives a full connection's worth of newline-delimited packets from
 * client_fd, appending each completed packet to DATA_FILE and writing the
 * full file content back to the client immediately after each packet.
 *
 * Returns 0 on normal connection close, -1 on fatal error.
 */
static int handle_client(int client_fd)
{
    char *buf = NULL;
    size_t buf_cap = 0;
    size_t buf_len = 0;
    char chunk[RECV_CHUNK_SIZE];
    ssize_t nread;

    for (;;)
    {
        nread = recv(client_fd, chunk, sizeof(chunk), 0);

        if (nread == 0)
        {
            /* Client closed connection */
            break;
        }
        if (nread == -1)
        {
            if (errno == EINTR)
            {
                /* Interrupted by our signal handler during shutdown */
                free(buf);
                return -1;
            }
            syslog(LOG_ERR, "recv failed: %s", strerror(errno));
            free(buf);
            return -1;
        }

        /* Grow the accumulation buffer to fit the new chunk */
        {
            size_t needed = buf_len + (size_t)nread;
            if (needed > buf_cap)
            {
                size_t new_cap = buf_cap == 0 ? RECV_CHUNK_SIZE : buf_cap;
                while (new_cap < needed)
                {
                    new_cap *= 2;
                }
                char *tmp = realloc(buf, new_cap);
                if (tmp == NULL)
                {
                    syslog(LOG_ERR, "malloc/realloc failed while buffering packet, discarding");
                    /* Discard what we have so far and reset, per assignment allowance */
                    free(buf);
                    buf = NULL;
                    buf_cap = 0;
                    buf_len = 0;
                    continue;
                }
                buf = tmp;
                buf_cap = new_cap;
            }
        }

        memcpy(buf + buf_len, chunk, (size_t)nread);
        buf_len += (size_t)nread;

        /* Process as many complete (newline-terminated) packets as we have */
        for (;;)
        {
            char *nl = memchr(buf, '\n', buf_len);
            if (nl == NULL)
            {
                break;
            }

            size_t packet_len = (size_t)(nl - buf) + 1; /* include the newline */

            /* Append this packet to the data file */
            int fd = open(DATA_FILE, O_WRONLY | O_CREAT | O_APPEND, 0644);
            if (fd == -1)
            {
                syslog(LOG_ERR, "open(%s) failed: %s", DATA_FILE, strerror(errno));
                free(buf);
                return -1;
            }

            size_t written = 0;
            while (written < packet_len)
            {
                ssize_t w = write(fd, buf + written, packet_len - written);
                if (w == -1)
                {
                    if (errno == EINTR)
                    {
                        continue;
                    }
                    syslog(LOG_ERR, "write(%s) failed: %s", DATA_FILE, strerror(errno));
                    close(fd);
                    free(buf);
                    return -1;
                }
                written += (size_t)w;
            }
            close(fd);

            /* Send the full file content back to the client */
            fd = open(DATA_FILE, O_RDONLY);
            if (fd == -1)
            {
                syslog(LOG_ERR, "open(%s) for read failed: %s", DATA_FILE, strerror(errno));
                free(buf);
                return -1;
            }

            char sendbuf[RECV_CHUNK_SIZE];
            ssize_t r;
            while ((r = read(fd, sendbuf, sizeof(sendbuf))) > 0)
            {
                ssize_t sent_total = 0;
                while (sent_total < r)
                {
                    ssize_t s = send(client_fd, sendbuf + sent_total, (size_t)(r - sent_total), 0);
                    if (s == -1)
                    {
                        if (errno == EINTR)
                        {
                            continue;
                        }
                        syslog(LOG_ERR, "send failed: %s", strerror(errno));
                        close(fd);
                        free(buf);
                        return -1;
                    }
                    sent_total += s;
                }
            }
            if (r == -1)
            {
                syslog(LOG_ERR, "read(%s) failed: %s", DATA_FILE, strerror(errno));
            }
            close(fd);

            /* Remove the processed packet from the front of buf */
            size_t remaining = buf_len - packet_len;
            memmove(buf, buf + packet_len, remaining);
            buf_len = remaining;
        }
    }

    free(buf);
    return 0;
}

static int daemonize(void)
{
    pid_t pid = fork();

    if (pid == -1)
    {
        syslog(LOG_ERR, "fork failed while daemonizing: %s", strerror(errno));
        return -1;
    }
    if (pid > 0)
    {
        /* Parent exits, letting the child continue as the daemon */
        exit(EXIT_SUCCESS);
    }

    /* Child continues here */
    if (setsid() == -1)
    {
        syslog(LOG_ERR, "setsid failed: %s", strerror(errno));
        return -1;
    }

    if (chdir("/") == -1)
    {
        syslog(LOG_ERR, "chdir(/) failed: %s", strerror(errno));
        return -1;
    }

    /* Redirect standard fds to /dev/null */
    int devnull = open("/dev/null", O_RDWR);
    if (devnull != -1)
    {
        dup2(devnull, STDIN_FILENO);
        dup2(devnull, STDOUT_FILENO);
        dup2(devnull, STDERR_FILENO);
        if (devnull > STDERR_FILENO)
        {
            close(devnull);
        }
    }

    return 0;
}

int main(int argc, char *argv[])
{
    bool run_as_daemon = false;

    if (argc > 1 && strcmp(argv[1], "-d") == 0)
    {
        run_as_daemon = true;
    }

    openlog("aesdsocket", LOG_PID, LOG_USER);

    if (setup_signal_handlers() == -1)
    {
        closelog();
        return -1;
    }

    g_listen_fd = create_and_bind_listen_socket();
    if (g_listen_fd == -1)
    {
        closelog();
        return -1;
    }

    if (run_as_daemon)
    {
        /* Fork happens only after a successful bind, per assignment requirement */
        if (daemonize() == -1)
        {
            close(g_listen_fd);
            closelog();
            return -1;
        }
    }

    while (!g_shutdown_requested)
    {
        struct sockaddr_storage client_addr;
        socklen_t addr_len = sizeof(client_addr);

        int client_fd = accept(g_listen_fd, (struct sockaddr *)&client_addr, &addr_len);
        if (client_fd == -1)
        {
            if (errno == EINTR || g_shutdown_requested)
            {
                break;
            }
            syslog(LOG_ERR, "accept failed: %s", strerror(errno));
            continue;
        }

        g_client_fd = client_fd;

        char ip_str[INET6_ADDRSTRLEN] = {0};
        if (client_addr.ss_family == AF_INET)
        {
            struct sockaddr_in *s = (struct sockaddr_in *)&client_addr;
            inet_ntop(AF_INET, &s->sin_addr, ip_str, sizeof(ip_str));
        }
        else if (client_addr.ss_family == AF_INET6)
        {
            struct sockaddr_in6 *s = (struct sockaddr_in6 *)&client_addr;
            inet_ntop(AF_INET6, &s->sin6_addr, ip_str, sizeof(ip_str));
        }
        else
        {
            strncpy(ip_str, "unknown", sizeof(ip_str) - 1);
        }

        syslog(LOG_INFO, "Accepted connection from %s", ip_str);

        handle_client(client_fd);

        syslog(LOG_INFO, "Closed connection from %s", ip_str);

        close(client_fd);
        g_client_fd = -1;
    }

    syslog(LOG_INFO, "Caught signal, exiting");

    if (g_listen_fd != -1)
    {
        close(g_listen_fd);
        g_listen_fd = -1;
    }

    if (remove(DATA_FILE) == -1 && errno != ENOENT)
    {
        syslog(LOG_ERR, "Failed to remove %s: %s", DATA_FILE, strerror(errno));
    }

    closelog();
    return 0;
}
```


---

## Step 3 — Generate SSH Key for Github Remote Deployment 

1. Generate a dedicated key for this purpose

```bash
ssh-keygen -t ed25519 -f ~/.ssh/aesd-deploy-key -C "aesd-buildroot-ci" -N ""
chmod 600 ~/.ssh/aesd-deploy-key
chmod 644 ~/.ssh/aesd-deploy-key.pub
```

This creates a private key (aesd-deploy-key) and public key (aesd-deploy-key.pub).

2. Add the public key to your aeld-assignment-3-and-later repo

This is the repo Buildroot's AESD_ASSIGNMENTS_SITE points to, so it needs read access there.

```bash
cat ~/.ssh/aesd-deploy-key.pub
```

Copy that output, then on GitHub:

* Go to 

https://github.com/cu-ecen-aeld/aeld-assignment-3-and-later/settings/keys

* Add deploy key
* Title: aesd-buildroot-ci
* Paste the public key
* Leave Allow write access unchecked (read-only, per your runbook's least-privilege rule)

3. Load it locally and verify

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/aesd-deploy-key
ssh-add -l
```

Then test read access specifically:

```bash
GIT_SSH_COMMAND="ssh -i ~/.ssh/aesd-deploy-key -o IdentitiesOnly=yes" \
  git ls-remote git@github.com:cu-ecen-aeld/aeld-assignment-3-and-later.git
```

## Step 3.1 — Verify the SSH remote URL before touching the `.mk` file

```bash
cd ~/Documents/aeld-assignment-3-and-later
git remote -v
```

Copy the exact SSH URL for `origin` (fetch line), e.g.:
```
git@github.com:cu-ecen-aeld/aeld-assignment-3-and-later.git
```

Confirm Buildroot's own git subprocess can authenticate with it (not just your
interactive shell):

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/<your-deploy-or-personal-key>
GIT_SSH_COMMAND="ssh -o IdentitiesOnly=yes" git ls-remote git@github.com:cu-ecen-aeld/aeld-assignment-3-and-later.git
```

A successful ref listing confirms this before it goes into the `.mk` file.

## Step 3.2 — Add it as a secret on the Buildroot repo (aeld-assignment-5), for CI

Since your self-hosted runner will also need this key when it runs ./build.sh in CI:

On your local terminal run the following:

```bash
cd ~/Documents/aeld-assignment-5
find . -path ./buildroot -prune -o -iname "*.yml" -print -o -iname "*.yaml" -print
```

(The -path ./buildroot -prune skips the huge Buildroot submodule so you're not wading through its internal CI files.)

That should turn up something like .github/workflows/build.yml or similar. Once you find it:

```bash
cat .github/workflows/<filename>.yml
```
Paste that content — I need to see specifically:

Any uses: webfactory/ssh-agent@... (or similar) step
The secrets.<NAME> reference it pulls the key from

The workflow expects a secret named exactly:

```bash
SSH_PRIVATE_KEY
```

```bash
cat ~/.ssh/aesd-deploy-key
```

* copy the full private key (including -----BEGIN... / -----END... lines)
* Go to https://github.com/prashantgautamofficial/aeld-assignment-5/settings/secrets/actions
* New repository secret
* Name it something your workflow YAML references (check your .github/workflows/*.yml for the exact secret name it expects `SSH_PRIVATE_KEY` — likely already set up from an earlier assignment)
* Paste the private key as the value

---

## Step 4 — Update `aesd-assignments.mk` in the new repo

```bash
cd ~/Documents/aeld-assignment-5
find . -iname "aesd-assignments.mk"
cat base_external/package/aesd-assignments/aesd-assignments.mk
```

Target shape of the file:

```make
################################################################################
#
# aesd-assignments
#
################################################################################

AESD_ASSIGNMENTS_VERSION = 555eede434d62471b030370f1e037f8bc3e46655
AESD_ASSIGNMENTS_SITE = git@github.com:cu-ecen-aeld/aeld-assignment-3-and-later.git
AESD_ASSIGNMENTS_SITE_METHOD = git
AESD_ASSIGNMENTS_GIT_SUBMODULES = YES

define AESD_ASSIGNMENTS_BUILD_CMDS
	$(MAKE) CC="$(TARGET_CC)" -C $(@D)/finder-app all
	$(MAKE) CC="$(TARGET_CC)" -C $(@D)/server all
endef

define AESD_ASSIGNMENTS_INSTALL_TARGET_CMDS
	$(INSTALL) -d 0755 $(@D)/conf/ $(TARGET_DIR)/etc/finder-app/conf/
	$(INSTALL) -m 0755 $(@D)/conf/* $(TARGET_DIR)/etc/finder-app/conf/
	$(INSTALL) -d 0755 $(TARGET_DIR)/usr/bin
	$(INSTALL) -m 0755 $(@D)/finder-app/writer $(TARGET_DIR)/usr/bin/writer
	$(INSTALL) -m 0755 $(@D)/finder-app/finder.sh $(TARGET_DIR)/usr/bin/finder.sh
	$(INSTALL) -m 0755 $(@D)/finder-app/finder-test.sh $(TARGET_DIR)/usr/bin/finder-test.sh
	$(INSTALL) -m 0755 $(@D)/assignment-autotest/test/assignment4/* $(TARGET_DIR)/bin/
	$(INSTALL) -m 0755 $(@D)/server/aesdsocket $(TARGET_DIR)/usr/bin/aesdsocket
	$(INSTALL) -m 0755 $(@D)/server/aesdsocket-start-stop $(TARGET_DIR)/etc/init.d/S99aesdsocket
endef

$(eval $(generic-package))
```

**Key points:**
- `AESD_ASSIGNMENTS_VERSION` must be an immutable commit hash, never a branch name.
  Update this value whenever `server/aesdsocket-start-stop` or `server/aesdsocket.c`
  changes and gets pushed — the `.mk` file's pin will otherwise silently build stale
  code.
- `CC="$(TARGET_CC)"` is passed explicitly in `BUILD_CMDS`.
- `server/Makefile` must honor `CC` (`CC ?= $(CROSS_COMPILE)gcc`) — verify:
  ```bash
  cat ~/Documents/aeld-assignment-3-and-later/server/Makefile | head -10
  ```
- `AESD_ASSIGNMENTS_GIT_SUBMODULES = YES` is only correct if
  `aeld-assignment-3-and-later` itself has git submodules. Confirm
  with `cat ~/Documents/aeld-assignment-3-and-later/.gitmodules`
  before assuming — if it has none, this line is harmless but unnecessary.

---

## Step 5 — Apply and sanity-check the `.mk` edit

```bash
export BR2_EXTERNAL=$(realpath base_external)
grep -i BR2_EXTERNAL buildroot/.config
```

## Step 5.1 — if `buildroot/.config` doesn't exist

Let's check what state the repo is actually in first:

### Check the repo layout

```bash
cd ~/Documents/aeld-assignment-5
ls -la
ls buildroot/ 2>&1 | head -5
ls base_external/configs/ 2>&1
```
```bash
aesd_qemu_defconfig
```

* If buildroot/ is empty or missing files, the submodule wasn't initialized — run:

```bash
git submodule update --init --recursive
```

* Look at base_external/configs/ for an existing defconfig (likely something like qemu_aesd_defconfig or similar, inherited from the assignment-4/base-external merge).

### Generate the initial .config

Once the submodule is populated, apply the existing defconfig so .config gets created:

```bash
export BR2_EXTERNAL=$(realpath base_external)
make -C buildroot aesd_qemu_defconfig
```

It should something like this:

```bash
BR2_EXTERNAL_NAMES="project_base"
BR2_EXTERNAL_project_base_PATH="/home/prashant/Documents/aeld-assignment-5/base_external"
BR2_EXTERNAL_project_base_VERSION="-g1110952-dirty"
```


Confirm the derived `BR2_EXTERNAL_<NAME>_PATH` case matches what's referenced in
`external.mk` / `Config.in`.

---

## Step 5.2 — CI: fix GitHub Actions submodule checkout for `buildroot`

If your `buildroot` submodule pin is a valid **tag** (e.g. `2024.02.13`) rather than a
branch, `git submodule update --init --recursive` and `actions/checkout`'s built-in
`submodules: recursive` option can both fail on a **fresh CI clone** with:

```
fatal: Needed a single revision
fatal: Unable to find current revision in submodule path 'buildroot'
```

**Root cause:** the pinned commit is only advertised by GitLab as a *peeled tag object*
(`refs/tags/2024.02.13^{}`), not as an independently fetchable bare SHA or branch tip.
GitLab's default server config (`uploadpack.allowReachableSHA1InWant` off) does not
allow `git fetch <remote> <bare-sha>` for such commits, even though the exact same SHA
works fine locally once your working copy already has the object cached from an
earlier `git submodule add` + `git checkout <tag>`.

**Also check `.gitmodules`** — a `branch = <tag-name>` entry (pointing at something
that is actually a tag, not a branch) makes this worse, since `git submodule sync`
will try to resolve it as a branch ref and fail outright:

```bash
cd ~/Documents/aeld-assignment-5
cat .gitmodules
```

If you see a `branch =` line under `[submodule "buildroot"]` pointing at a tag name,
remove it:

```bash
git config -f .gitmodules --unset submodule.buildroot.branch
git add .gitmodules
git commit -m "fix: remove invalid branch ref from .gitmodules for buildroot submodule (tag, not branch)"
```

**Fix — bypass `git submodule update`'s automatic SHA fetch for `buildroot` entirely.**
Verify this sequence locally first (safe to test against a throwaway clone):

```bash
rm -rf /tmp/test-clone
git clone https://github.com/prashantgautamofficial/aeld-assignment-5.git /tmp/test-clone
cd /tmp/test-clone

git submodule sync --recursive
git submodule update --init assignment-autotest
git -C assignment-autotest submodule update --init --recursive

mkdir -p buildroot
git -C buildroot init -q
git -C buildroot remote add origin https://gitlab.com/buildroot.org/buildroot.git \
  2>/dev/null || git -C buildroot remote set-url origin https://gitlab.com/buildroot.org/buildroot.git
git -C buildroot fetch --tags origin
git -C buildroot checkout 2024.02.13
```

`HEAD is now at <pinned-sha>` confirms success. Once verified locally, put the same
sequence into the GitHub Actions workflow:

```bash
cat .github/workflows/*.yml
```

Replace (or add) the submodule checkout step with:

```yaml
name: assignment-test
on:
  push:
    tags-ignore:
      - '*'
    branches:
      - '*'
jobs:
  full-test:
    container: cuaesd/aesd-autotest:24-assignment5-buildroot
    runs-on: self-hosted
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Checkout submodules
        run: |
          git submodule sync --recursive
          git submodule update --init assignment-autotest
          git -C assignment-autotest submodule update --init --recursive
          mkdir -p buildroot
          git -C buildroot init -q
          git -C buildroot remote add origin https://gitlab.com/buildroot.org/buildroot.git 2>/dev/null || git -C buildroot remote set-url origin https://gitlab.com/buildroot.org/buildroot.git
          git -C buildroot fetch --tags origin
          git -C buildroot checkout 2024.02.13
      - uses: webfactory/ssh-agent@v0.5.3
        with:
          ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}
      - name: Run full test
        env:
          GIT_SSH_COMMAND: "ssh -o StrictHostKeyChecking=no"
        run: ./full-test.sh
      - name: Cleanup
        if: always()
        run: |
          ssh-add -D
```

**Notes / gotchas hit while debugging this:**
- `actions/checkout@v2` is too old for reliable `submodules:`/`fetch-depth:` handling —
  use `@v4`.
- YAML is whitespace-sensitive and does **not** allow tab characters for indentation.
  If editing with `gedit`/`nano` and something mysteriously fails with a `ScannerError`
  or `ParserError`, check for stray tabs:
  ```bash
  cat -A .github/workflows/*.yml | grep -c '\^I'   # should print 0
  ```
- The self-hosted runner's workspace can persist between runs. A prior partial run can
  leave `buildroot/` already `git init`-ed with `origin` set, which makes a plain
  `git -C buildroot remote add origin ...` fail with `remote origin already exists` on
  the *next* run. Make it idempotent with `... || git -C buildroot remote set-url ...`
  as shown above.
- Always validate YAML before pushing to avoid burning a CI run on a syntax typo:
  ```bash
  python3 -c "import yaml; yaml.safe_load(open('.github/workflows/github-actions.yml'))" && echo "YAML OK"
  ```

Commit and push once verified:

```bash
git add .github/workflows/*.yml
git commit -m "ci: fix buildroot submodule checkout on fresh clone (GitLab disallows fetch-by-arbitrary-SHA)"
git push origin main
```

Check the **Actions** tab and confirm the `Checkout submodules` step goes green before
moving on.

---

## Step 6 — Update `runqemu.sh` for port forwarding

```bash
cat runqemu.sh
```

Find the QEMU network invocation line, e.g.:

```bash
-netdev user,id=eth0,hostfwd=tcp::10022-:22 \
```

Add a second `hostfwd` clause for port 9000, so it becomes:

```bash
-netdev user,id=eth0,hostfwd=tcp::10022-:22,hostfwd=tcp::9000-:9000 \
```

Apply with `sed` (adjust the device id `eth0` if yours differs — check what `cat
runqemu.sh` actually showed):

```bash
sed -i 's/hostfwd=tcp::10022-:22 \\/hostfwd=tcp::10022-:22,hostfwd=tcp::9000-:9000 \\/' runqemu.sh
```

Verify the edit landed correctly:

```bash
grep hostfwd runqemu.sh
```

This forwards host port 9000 → guest port 9000, and host port 10022 → guest port 22
(SSH).

---

## Step 7 — Build and boot

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/aesd-deploy-key
ssh-add -l
./build.sh
```

```bash
./runqemu.sh
```

In another terminal, verify SSH port-forward:

```bash
ssh -p 10022 root@localhost
```

**If you see `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`** — this is expected,
not a real security issue. Each fresh QEMU build regenerates a new SSH host key, but
your host's `known_hosts` still has the old one cached from a previous boot. Clear it:

```bash
ssh-keygen -f "/home/prashant/.ssh/known_hosts" -R "[localhost]:10022"
```

Then reconnect:

```bash
ssh -p 10022 root@localhost
```

You'll be prompted to accept the new host key the first time — type `yes`.

Since you'll repeat this after every rebuild through Step 8's shutdown/restart test,
consider an alias that skips host-key checking for this specific local dev target only:

```bash
alias qemussh='ssh -p 10022 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@localhost'
```

Verify the socket server auto-started. Note: BusyBox's minimal `netstat` does not
support the `-p` (show process) flag — use:

```bash
ps | grep aesdsocket
netstat -tln | grep 9000
```

If BusyBox doesn't include `nc` (netcat) as an applet, test the socket **from the
host** instead, using the port-9000 forward:

```bash
# on host, separate terminal
echo "test data" | nc localhost 9000
# if host nc is missing: sudo apt-get install -y netcat-openbsd
```

Then confirm on the QEMU side:

```bash
cat /var/tmp/aesdsocketdata
```

---

## Step 8 — Run the test suite and verify graceful shutdown persistence

```bash
./full-test.sh
```

Test the shutdown/restart requirement (no data from a previous run should persist):

```bash
# inside qemu
poweroff -f

# host: restart
./runqemu.sh

# reconnect and check /var/tmp/aesdsocketdata is fresh, not appended from prior boot
```

---

## Step 9 — Tag and push

**Check what's actually about to be committed first** — avoid accidentally staging
build artifacts, a dirty `buildroot/` submodule pointer, or `buildroot/output/`:

```bash
cd ~/Documents/aeld-assignment-5
git status
```

If anything unexpected shows up (e.g. `buildroot` listed as modified content, stray
`*.o`/`output/` paths), address it before committing — check `.gitignore` covers
build artifacts, and confirm `buildroot`'s checked-out SHA still matches what's
recorded in the superproject tree (`git submodule status`).

```bash
git add -A
git commit -m "Assignment 5 Part 2: socket server init script, buildroot package, port forwarding"
git push origin main

git tag -a assignment-5-complete -m "Assignment 5 complete"
git push origin assignment-5-complete
```

Also tag the server-app repo (`aeld-assignment-3-and-later`) if
required by course convention — check the assignment's linked tagging guide.

---

## Verification Checklist

| # | Requirement | Verified via |
|---|---|---|
| 1 | `aesd-assignments` package cross-compiles `aesdsocket` from `server/` | Step 4, 7 |
| 2 | `aesdsocket` installed to `/usr/bin` | Step 4, 7 |
| 3 | `aesdsocket-start-stop` installed to `/etc/init.d/S99aesdsocket` | Step 2, 4, 7 |
| 4 | `buildroot` submodule checks out cleanly on a fresh CI clone | Step 5.2 |
| 5 | Host port 9000 forwarded to guest port 9000 | Step 6, 7 |
| 6 | Host port 10022 forwarded to guest port 22 (SSH) | Step 6, 7 |
| 7 | Socket server starts automatically on boot | Step 7 |
| 8 | `full-test.sh` passes against QEMU target | Step 8 |
| 9 | Graceful shutdown (halt) clears state; no stale data on restart | Step 8 |
| 10 | GitHub Actions CI passes end-to-end | Step 5.2 |
| 11 | Submission tagged `assignment-5-complete` | Step 9 |

---

## Correctness notes from review

A few things worth double-checking rather than taking on faith, since they weren't
independently verified during this session:

- **`AESD_ASSIGNMENTS_VERSION` pin (`555eede4...`)** — this must be updated any time
  `aesdsocket.c`, `aesdsocket-start-stop`, or `server/Makefile` change and get pushed
  to `aeld-assignment-3-and-later`. A stale pin will silently build
  old code with no error.
- **`AESD_ASSIGNMENTS_GIT_SUBMODULES = YES`** in the `.mk` — only needed if that repo
  itself has submodules (e.g. `assignment-autotest`). Confirm with
  `cat .gitmodules` in that repo; if there are none, this line does nothing harmful
  but is worth pruning for clarity.
- **`aesdsocket.c`'s `-d` daemon behavior**: the code forks *after* a successful
  `bind()`/`listen()`, per the assignment's requirement, and the parent exits via
  `exit(EXIT_SUCCESS)` — worth a final read-through to confirm this still matches
  whatever version is at the pinned commit, since local edits and the pinned SHA can
  drift apart.
- **Two install-target command blocks appear in this document** (an early, simpler
  one under Step 4's "target shape" example, and a fuller one further down installing
  both `finder-app` and `server` outputs). Make sure the `.mk` file you actually apply
  is the fuller version — the one installing `writer`, `finder.sh`, `finder-test.sh`,
  the assignment-autotest scripts, **and** `aesdsocket`/`aesdsocket-start-stop` — since
  Assignment 5 builds on top of Assignment 4's finder-app requirements, not a
  replacement for them.
- **Image references removed**: the original draft referenced local screenshot files
  (`image.png`, `image-1.png`, etc.) that aren't embedded in this document and won't
  resolve for anyone else reading it. Re-attach actual screenshots if you want them
  preserved, or leave prose-only as done here.
