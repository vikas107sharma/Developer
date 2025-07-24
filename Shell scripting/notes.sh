#!/bin/bash

# ============================
# Shell Scripting Notes Script
# ============================

# chmod (change mode) is used to set permissions for files and directories.
# Example:
# chmod 754 hello.sh

# Breakdown of 754:
# 7 => rwx (Owner: read + write + execute)
# 5 => r-x (Group: read + execute)
# 4 => r-- (Others: read only)

echo "========= chmod Explanation ========="
echo "chmod 754 file:"
echo "Owner (7): rwx (read, write, execute)"
echo "Group (5): r-x (read, execute)"
echo "Others (4): r-- (read only)"
echo

# ============================
# Basic Echo & Date
# ============================

echo "========= Basic Echo & Date ========="
name="your system"
echo "I am $name, Today is $(date)"
echo

# ============================
# Taking User Input
# ============================

echo "========= Read User Input ========="
echo "Enter your name:"
read username
echo "Your name is $username"
echo

# ============================
# Script Arguments
# ============================

echo "========= Script Arguments ========="
# Example run: ./shell_notes.sh arg1 arg2
echo "Script Name: $0"
echo "Argument 1: $1"
echo "Argument 2: $2"
echo

# ============================
# if-else-elif Example
# ============================

echo "========= if-else-elif Example ========="
echo "Enter a number:"
read num

if (( num < 0 )); then
  echo "Negative number"
elif (( num == 0 )); then
  echo "Zero"
else
  echo "Positive number"
fi
echo

# ============================
# Loops: Creating and Deleting Files
# ============================

echo "========= Loop: Create Files ========="
for ((i=0; i<5; i++)); do
  touch "demo$i.txt"
  echo "Created demo$i.txt"
done

echo "Files created: $(ls demo*.txt)"
echo

# Cleanup
echo "========= Cleaning Up ========="
rm -f demo*.txt
echo "Temporary files deleted."
echo


# Crobtab

# 1. Manual Test
/usr/bin/python3 "/mnt/d/Developer/Shell scripting/file_writer.py"

# add cron
* * * * * /usr/bin/python3 "/mnt/d/Developer/Shell scripting/file_writer.py"

# 2. Show current crontab
crontab -l

# 3. Edit cron
crontab -e

# 4. Remove cron
crontab -r

# ============================
# End of Script
# ============================

echo "========= Script Complete ========="

