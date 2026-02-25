# Excel with Dell (Team 7)
---
## Members

**Daniel Omoregie**  
University of Houston  

**Makena Brown**  
Northeastern University  

**Sathvik Dantuluri**  
University of Massachusetts Amherst  

**Landon Rodrigues**  
Northeastern University  

**Mayank V Konduri**  
The University of Texas at Austin  

---

## Dell Advisors

**Mr. Bryan Kemp**  
Enterprise Technology Principal Engineer at Dell, Inc.

**Mrs. Sarah Edwards**  
Project/Program Manager, Global L&D Strategy and Planning

---

# Project Setup Guide

Follow these steps to get the project running locally.

---

## 1️⃣ Install VS Code

Download and install:

https://code.visualstudio.com/

### Recommended Extensions (CTRL + SHIFT + X)

Open VS Code → Extensions → Install:

- Python
- Python Debugger
- Pylance
- Python Environments
  
---

## 2️⃣ Install GitHub Desktop

Download:

https://desktop.github.com/

Then:

1. Sign in using your GitHub account
2. Clone this repository
3. Click **Open in Visual Studio Code**

---

## 3️⃣ Open the Project Properly

When VS Code opens:

- Keep the `src` project folder open
- Close all other folders

---

## 4️⃣ Install Dependencies

With the virtual environment activated:

```bash
python -m pip install -r requirements.txt
```

This installs all required packages for the project.

---

## 5️⃣ Test the Project (No Neon Required)

You can run core project files without setting up Neon.

To test the base setup (click the play button in the file):

`Hello_World.py`

If everything is installed correctly, you should see:

```bash
Connected to Neon Hosted Server!
Hello World!
Thank you for being responsible! :)
```

If you see errors, make sure:
- You ran `python -m pip install -r requirements.txt`

---

## 6️⃣ (Optional) Set Up Neon Database

⚠ This step is ONLY required if you want to:
- Visualize the datasets
- Connect to the live PostgreSQL database
- Work with hosted data

You can still develop locally without this.

---

## Create a Neon Account

Go to:

https://neon.tech

Click **Sign Up with GitHub**

---

## Accept the Project Invite

You will receive an email invitation to join the shared Neon project.

Accept the invitation.

---

## Verify Database Access

Once added:

1. Open the Neon dashboard
2. Confirm you can see the shared project
3. Click on 'Tables' on the left, and make sure you can see the datasets

Note: No need to create a `.env` file, it is already included in this repository.

You're now ready to work on the project 🚀
