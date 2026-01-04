#!/bin/bash

# 🗂 Basic File & Directory Commands

ls                  # List files in current folder
cd foldername       # Change into a folder
cd ..               # Go back one folder
pwd                 # Show current working directory
mkdir newfolder     # Make a new folder
touch file.txt      # Create a new file
rm file.txt         # Delete a file
rm -r foldername    # Delete a folder and everything inside it

# 🔍 Viewing Files

cat file.txt        # Show file content
vim file.txt        # Show file content and edit

# 🔧 System Info

whoami              # Show your username
df -h               # Show disk space usage in human-readable format

# 🌐 Network

ping google.com     # Check internet connection
ip a                # Show your IP address and network info
curl ifconfig.me    # Get your public IP address

# 🛠 Package Management (Ubuntu/Debian)
# sudo stands for "superuser do" — it lets a normal user run commands as the root (admin) user.

sudo apt update                         # Check for available updates
sudo apt upgrade                        # Install updates for installed packages
sudo apt install packagename            # Install a new package (example: sudo apt install curl)

sudo cmd	                # Run just one command as root	Safer, limited privilege
sudo su               	    # Switch to full root shell	Admin wants full root access

rm -f demo*.txt            # Remove files like demo
rm -r folder_name          # Remove folder





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

