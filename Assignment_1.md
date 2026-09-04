# AESD Assignment 1 - Search string finder app `finder.sh` and string writer app `writer.sh`

## `finder.sh`

* Accepts the following runtime arguments: the first argument is a path to a directory on the filesystem, referred to below as filesdir; the second argument is a text string which will be searched within these files, referred to below as searchstr

* Exits with return value 1 error and print statements if any of the parameters above were not specified

* Exits with return value 1 error and print statements if filesdir does not represent a directory on the filesystem

* Prints a message "The number of files are X and the number of matching lines are Y" where X is the number of files in the directory and all subdirectories and Y is the number of matching lines found in respective files, where a matching line refers to a line which contains searchstr (and may also contain additional content).

```bash
#!/bin/sh

# Validate required arguments
if [ $# -ne 2 ]; then
    echo "Error: expected 2 arguments: <filesdir> <searchstr>" >&2
    exit 1
fi

filesdir=$1
searchstr=$2

# Validate filesdir exists and is a directory
if [ ! -d "$filesdir" ]; then
    echo "Error: '$filesdir' is not a directory" >&2
    exit 1
fi

# Count files in directory and subdirectories
file_count=$(find "$filesdir" -type f | wc -l)

# Count matching lines in files with the given search string
match_count=$(grep -R -n -F -- "$searchstr" "$filesdir" 2>/dev/null | wc -l)

# Print required summary message
echo "The number of files are $file_count and the number of matching lines are $match_count"

exit 0
```

## `writer.sh`

* Accepts the following arguments: the first argument is a full path to a file (including filename) on the filesystem, referred to below as writefile; the second argument is a text string which will be written within this file, referred to below as writestr

* Exits with value 1 error and print statements if any of the arguments above were not specified

* Creates a new file with name and path writefile with content writestr, overwriting any existing file and creating the path if it doesn’t exist. Exits with value 1 and error print statement if the file could not be created.

```bash
#!/bin/sh

# Validate required arguments
if [ $# -ne 2 ]; then
    echo "Error: expected 2 arguments: <writefile> <writestr>" >&2
    exit 1
fi

writefile=$1
writestr=$2

# Create parent directory if it does not exist
mkdir -p "$(dirname "$writefile")" || {
    echo "Error: could not create directory for '$writefile'" >&2
    exit 1
}

# Write the content to the file, overwriting any existing file
printf '%s' "$writestr" > "$writefile" || {
    echo "Error: could not create file '$writefile'" >&2
    exit 1
}

exit 0
```

