# Embedded Linux Assignments Collection

This folder contains the course notes and assignment guides for the Embedded Linux / Linux System Programming and Buildroot learning track. The material is organized as a progression of practical labs covering shell scripting, Git/GitHub workflow, system calls, kernel/root filesystem builds, threading, and Buildroot-based embedded Linux images.

## File-by-file purpose

### Assignment_1.md
Purpose: Introductory assignment on Linux shell scripting and filesystem operations.

Covers:
- implementing `finder.sh` to count files and matching lines recursively
- implementing `writer.sh` to create or overwrite a file and its parent directories
- validation rules, return codes, and expected script behavior

### Assignment_2.md
Purpose: GitHub repository setup and ARM cross-compilation setup guide.

Covers:
- generating and adding an SSH key for GitHub access
- updating remotes and preparing the assignment repository
- installing the ARM cross-toolchain (`aarch64-none-linux-gnu`)
- generating cross-compile metadata and adjusting the assignment test script

### Assignment_3.1.md
Purpose: System calls and process creation exercise.

Covers:
- repository setup for Assignment 3 Part 1
- updating the finder test script for the new workflow
- implementing `system()` and `exec()` logic in the system calls example
- running Unity unit tests to validate the implementation

### Assignment_3.2.md
Purpose: Manual Linux kernel and root filesystem build.

Covers:
- pulling in assignment 3 part 2 starter code
- building a Linux kernel for ARM64 using `make defconfig` and `make all`
- creating a minimal root filesystem layout
- cloning and configuring BusyBox
- compiling BusyBox and installing it into the target rootfs
- copying required libraries and device nodes
- copying the finder app utilities into the target filesystem

### Assignment_4.1.md
Purpose: Threading and synchronization assignment.

Covers:
- merging the Assignment 4 starter code into the project repo
- implementing the threading logic in the example C source
- working with mutexes and thread start functions
- running unit tests for the pthread implementation
- tagging and pushing the completed repository version

### Assignment_4.2.md
Purpose: Buildroot environment bring-up and full embedded Linux image workflow.

Covers:
- setting up required host packages for Buildroot
- creating a clean Assignment 4 repo and merging the base starter content
- adding the Buildroot submodule pinned to a specific release
- generating and saving a defconfig
- building a QEMU aarch64 image
- configuring rootfs and runtime components
- preparing the embedded image for testing via QEMU and SSH

### Github_Action_Runner.md
Purpose: Guide for configuring and using a GitHub Actions self-hosted runner.

Covers:
- setting up the runner environment
- registering a runner with GitHub
- running the service and validating availability
- using it in CI/CD workflows for course assignments/projects

### organize_md_images.py
Purpose: Utility script for organizing image references inside Markdown files.

What it does:
- finds local image links used in `.md` files
- moves them into a shared images directory
- updates the markdown references to the new paths
- supports single-file and recursive processing modes
- preserves backups before rewriting files

This script was used to standardize the image storage and keep references consistent across the assignment notes.

### assets/
Purpose: Stores the images used by the Markdown assignment files.

These files include screenshots and diagrams referenced from the course instructions, such as SSH setup, Git workflow, and Buildroot output examples.

### backup-md/
Purpose: Backup copies of earlier Markdown files kept before image organization changes.

These files preserve the original content and are useful if you need to compare the pre-cleanup version of an assignment with the updated version.

---

## Recommended reading order

1. Assignment_1.md
2. Assignment_2.md
3. Assignment_3.1.md
4. Assignment_3.2.md
5. Assignment_4.1.md
6. Assignment_4.2.md

This sequence follows the progression from basic shell scripting and Git setup through system calls, kernel and rootfs build steps, and finally Buildroot-based embedded Linux image creation.
