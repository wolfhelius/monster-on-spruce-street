# The Monster on Spruce Street

Informational site for neighbors regarding the proposed 30-unit development at 86–96 Spruce Street, Princeton NJ (Ordinance #2026-07 / AH-12 rezoning).

**Live site:** https://yourusername.github.io/giant-on-spruce-street/

---

## Setup

### First time

1. [Create a GitHub account](https://github.com) if you don't have one
2. Create a new repository named `giant-on-spruce-street` (or whatever you prefer)
3. Upload these files, or clone and push:
   ```bash
   git clone https://github.com/yourusername/giant-on-spruce-street
   # copy these files in
   git add .
   git commit -m "Initial site"
   git push
   ```
4. Go to **Settings → Pages** in your GitHub repo
5. Under **Source**, select `Deploy from a branch` → `main` → `/ (root)`
6. Click Save — your site will be live at `https://yourusername.github.io/giant-on-spruce-street/` within a minute or two

### Custom domain (optional)

1. Buy a domain (e.g. `monsteronsprucestreet.com`) from Namecheap (~$10/yr)
2. In Namecheap DNS settings, add these records:
   ```
   A     @    185.199.108.153
   A     @    185.199.109.153
   A     @    185.199.110.153
   A     @    185.199.111.153
   CNAME www  yourusername.github.io
   ```
3. In GitHub repo Settings → Pages, enter your custom domain
4. Update `url` and `baseurl` in `_config.yml`:
   ```yaml
   url: "https://monsteronsprucestreet.com"
   baseurl: ""
   ```

---

## Adding content

### Add a document

1. Place PDF in `docs/` folder
2. Add a row to the table in `documents.md`:
   ```markdown
   | [Title](docs/filename.pdf) | Description |
   ```
3. Commit and push

### Add a figure

1. Place image (PNG, JPG) in `fig/` folder
2. Embed in any markdown page:
   ```markdown
   ![Alt text](fig/filename.png)
   *Figure 1: Caption*
   ```

### Add a new page

1. Create `new-page.md` in the root folder
2. Add front matter at the top:
   ```yaml
   ---
   layout: default
   title: Page Title
   nav_order: 5
   ---
   ```
3. Write content in Markdown below the front matter

---

## File structure

```
giant-on-spruce-street/
├── index.md              ← Main page (Dear Neighbor letter)
├── master-plan.md        ← Master Plan inconsistencies analysis
├── documents.md          ← Document index
├── about.md              ← FAQ
├── fig/                  ← Images and figures
├── docs/                 ← PDFs (add your documents here)
├── _config.yml           ← Site configuration
├── Gemfile               ← Ruby dependencies
└── README.md             ← This file
```

---

## Contact

Adam Wolf · 82 Spruce Street, Princeton NJ 08540  
adam.von.wolfhausen@gmail.com · 609-480-2491
