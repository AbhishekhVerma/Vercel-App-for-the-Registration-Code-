# Course Timetable Scheduler (Web App)

*Note: This repository builds upon our previous core python scheduler repository, specifically wrapping and adapting the clash-detection logic into a full-stack, serverless web app designed to be deployed directly on Vercel.*

A modern, serverless web application to help university students automate their course registration planning. This app checks for scheduling conflicts (both class times and Midsem/Compre exam dates) between core courses and electives, and provides a real-time interactive timetable visualizer.

## Tech Stack

- **Frontend:** HTML, Tailwind CSS, Vue.js (CDN)
- **Backend:** Python, Flask, Pandas (Vercel Serverless Functions)
- **Deployment:** Vercel

## Deployment Instructions

This repository is pre-configured to be deployed on [Vercel](https://vercel.com/) with zero configuration required.

### Deploy via GitHub (Recommended)
1. Push this folder to a GitHub repository.
2. Go to Vercel and select **"Add New Project"**.
3. Import your GitHub repository.
4. Click **Deploy**. Vercel will automatically detect the Python backend and route it correctly using `vercel.json`.

### Deploy via Vercel CLI
If you have Node.js installed, you can deploy directly from your terminal:
```bash
npm i -g vercel
vercel
vercel --prod
```

## How It Works

1. Users upload their `Main.xlsx` file containing their core timetable and course catalog.
2. The frontend sends the file to the `/api/analyze` Python serverless function.
3. The backend calculates overlaps and exam clashes using Pandas.
4. The Vue.js frontend renders the available courses (highlighting clashes in red) and allows the user to interactively click checkboxes to build their final schedule.
5. The final schedule handles course IDs by converting them to full, human-readable course names on the grid.
