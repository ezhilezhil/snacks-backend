# Zentegra Friday Snacks - Python FastAPI Backend

This Python backend connects to your Hostinger MySQL database (`u373142447_friday`) and is pre-configured for free instant deployment on **Render** or **Vercel**.

---

## 🚀 How to Deploy on Render (Recommended, 2 Minutes)

1. Push this `backend-python` folder to a GitHub repository (e.g. `zentegra-snacks-backend`).
2. Log in to [render.com](https://render.com) and click **New +** $\rightarrow$ **Web Service**.
3. Select your repository.
4. Render will auto-detect Python. Verify the settings:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `DB_HOST`: Your Hostinger Remote MySQL IP / Hostname (from Hostinger hPanel -> Remote MySQL)
   - `DB_PORT`: `3306`
   - `DB_NAME`: `u373142447_friday`
   - `DB_USER`: `u373142447_snacks`
   - `DB_PASSWORD`: Your MySQL database password
6. Click **Deploy Web Service**.
7. Once deployed, Render will give you a public URL (e.g. `https://zentegra-snacks-api.onrender.com`).

---

## 🔗 Connecting to Frontend on Hostinger

1. Open `src/config.js` in the frontend and set:
   ```javascript
   export const BACKEND_URL = 'https://your-app-name.onrender.com';
   ```
2. Run `npm run build`.
3. Upload the contents of the `dist/` folder directly into your Hostinger website (`utax.online` -> `public_html`).
