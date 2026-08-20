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

Instead of relying strictly on uploading complex Excel sheets like the original Python script, this web app provides a sleek, zero-friction interface:

1. **Smart Grid Input:** Users manually construct their core timetable in the interactive web grid. 
   - **Spreadsheet Shortcuts:** You can navigate the grid using arrow keys (just like Excel/Sheets).
   - **Smart Paste:** Copy a block of courses from Excel and paste it directly into the web grid—the app will automatically parse and map the data into the correct slots!
2. **Built-in Master Database:** The app uses a pre-loaded `data.xlsx` catalog on the server backend, so users no longer have to upload the master catalog themselves.
3. **Dynamic Evaluation:** Once the core timetable is filled in, the Python backend maps your inputted course IDs (e.g. `CS F372`) to their full titles and instantly identifies clashes (time clashes and Midsem/Compre clashes) across all available Disciplinary and Humanities courses.
4. **Interactive Visualizer:** You can interactively tick checkboxes on valid, non-clashing electives to append them to your live Timetable Visualizer at the bottom of the page.
5. **Custom Uploads:** While defaults are provided, users can still optionally upload their own Master Database, Humanities lists, or Disciplinary lists via the web UI.
