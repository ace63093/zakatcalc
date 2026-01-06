# How to Deploy Zakat Calculator to DigitalOcean

This guide will help you put your Zakat Calculator on the internet so anyone can use it!

## What You Need Before Starting

1. A **DigitalOcean account** (sign up at digitalocean.com)
2. Your **GitHub account** connected to DigitalOcean
3. Your **Cloudflare R2** bucket info (you already have this!)
4. About **10 minutes** of time

---

## Step 1: Connect GitHub to DigitalOcean

1. Go to [cloud.digitalocean.com](https://cloud.digitalocean.com)
2. Click the **green "Create" button** at the top
3. Click **"Apps"**
4. Click **"GitHub"** as your source
5. If asked, click **"Connect GitHub"** and allow access
6. Find and select your repo: **ace63093/zakatcalc**
7. Select the **production** branch
8. Click **Next**

---

## Step 2: Configure Your App

### Basic Settings
- **Name:** `zakat-calculator` (or whatever you want)
- **Region:** `Toronto` (closest to you)
- **Branch:** `production`

### Plan
- Pick the **$5/month Basic** plan (it's the cheapest and works fine!)

### Environment Variables (IMPORTANT!)

You need to add these secret values. Click "Edit" next to Environment Variables and add:

| Variable Name | What to Put | Is it Secret? |
|---------------|-------------|---------------|
| `SECRET_KEY` | Make up a long random password (like `xK9#mP2$vL5@nQ8`) | YES (click "Encrypt") |
| `R2_BUCKET` | `na-west` | YES |
| `R2_ENDPOINT_URL` | `https://5868b2451eb49a65bc168ce4ab7cb5f8.r2.cloudflarestorage.com` | YES |
| `R2_ACCESS_KEY_ID` | Your R2 access key | YES |
| `R2_SECRET_ACCESS_KEY` | Your R2 secret key | YES |

These should already be set (leave them alone):
- `FLASK_ENV` = `production`
- `DATA_DIR` = `/app/data`
- `PRICING_BACKGROUND_SYNC` = `1`
- `PRICING_ALLOW_NETWORK` = `1`
- `R2_ENABLED` = `1`
- `R2_PREFIX` = `zakat-app/pricing/`

---

## Step 3: Deploy!

1. Click **"Next"** until you see the Review page
2. Double-check everything looks right
3. Click the big **"Create Resources"** button
4. Wait about 5 minutes while it builds

You'll see a progress bar. When it turns green, your app is live!

---

## Step 4: Test Your App

1. DigitalOcean will give you a URL like `zakat-calculator-xxxxx.ondigitalocean.app`
2. Click it to open your app
3. Try entering some numbers to make sure it works!

---

## Step 5: Add Your Custom Domains

Now let's make your app work with `whatismyzakat.ca` and `whatismyzakat.com`!

### In DigitalOcean:

1. Go to your app in DigitalOcean
2. Click **"Settings"** tab
3. Click **"Domains"** on the left
4. Click **"Add Domain"**
5. Add these one at a time:
   - `whatismyzakat.ca`
   - `www.whatismyzakat.ca`
   - `whatismyzakat.com`
   - `www.whatismyzakat.com`

### In Cloudflare (for each domain):

1. Log into [Cloudflare](https://dash.cloudflare.com)
2. Click on your domain (like `whatismyzakat.ca`)
3. Click **"DNS"** on the left
4. Delete any old A or AAAA records for `@` and `www`
5. Add new records:

**For the main domain (whatismyzakat.ca):**
| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `@` | `zakat-calculator-xxxxx.ondigitalocean.app` | Orange cloud ON |

**For www:**
| Type | Name | Target | Proxy |
|------|------|--------|-------|
| CNAME | `www` | `zakat-calculator-xxxxx.ondigitalocean.app` | Orange cloud ON |

6. Repeat for `whatismyzakat.com`

Wait about 5-10 minutes, then try visiting your domains!

---

## Step 6: Turn on HTTPS (Already Done!)

Good news: DigitalOcean automatically gives you HTTPS (the lock icon) for free!

Just make sure in Cloudflare:
1. Go to **SSL/TLS** settings
2. Set mode to **"Full (strict)"**

---

## If Something Goes Wrong

### App won't start?
- Check the **"Runtime Logs"** in DigitalOcean
- Make sure all your environment variables are set correctly

### Domain not working?
- Wait 10 minutes (DNS takes time)
- Check Cloudflare DNS records are correct
- Make sure proxy (orange cloud) is ON

### Prices not loading?
- Check R2 credentials are correct
- Check the logs for error messages

---

## Costs

- **DigitalOcean App:** ~$5/month
- **Cloudflare R2:** Free for small usage (you won't hit limits)
- **Domains:** Whatever you paid for them

Total: About **$5/month** to run your Zakat Calculator!

---

## Updating Your App

When you make changes:

1. Commit your code changes
2. Push to the `production` branch:
   ```bash
   git checkout production
   git merge main
   git push origin production
   ```
3. DigitalOcean will automatically rebuild and deploy!

---

## Quick Reference

| What | Where |
|------|-------|
| App Dashboard | cloud.digitalocean.com → Apps |
| Logs | App → Runtime Logs |
| Environment Variables | App → Settings → Environment Variables |
| Domains | App → Settings → Domains |
| Cloudflare DNS | dash.cloudflare.com → Your Domain → DNS |

---

## Need Help?

- DigitalOcean Docs: https://docs.digitalocean.com/products/app-platform/
- Cloudflare Docs: https://developers.cloudflare.com/dns/

You did it! Your Zakat Calculator is now on the internet! 🎉
