# The Monster on Spruce Street

Informational site for neighbors regarding the proposed 30-unit development at 86–96 Spruce Street, Princeton NJ (Ordinance #2026-07 / AH-12 rezoning).

**Live site:** https://wolfhelius.github.io/monster-on-spruce-street/

---

## Setup

### First time

1. Clone the repo:
   ```bash
   git clone https://github.com/wolfhelius/monster-on-spruce-street
   cd monster-on-spruce-street
   ```
2. Make changes, then commit and push:
   ```bash
   git add .
   git commit -m "Update site"
   git push
   ```
3. GitHub Pages is configured under **Settings → Pages** to deploy from the `main` branch (root). The site updates automatically within a minute or two of each push at `https://wolfhelius.github.io/monster-on-spruce-street/`.

### Custom domain (optional)

1. Buy a domain (e.g. `monsteronsprucestreet.com`) from Namecheap (~$10/yr)
2. In Namecheap DNS settings, add these records:
   ```
   A     @    185.199.108.153
   A     @    185.199.109.153
   A     @    185.199.110.153
   A     @    185.199.111.153
   CNAME www  wolfhelius.github.io
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
monster-on-spruce-street/
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
