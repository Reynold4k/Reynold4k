# Deployment

This directory is a ready-to-publish GitHub profile repository for
`Reynold4k`.

## Publish the profile

1. On GitHub, create a **public** repository named exactly `Reynold4k` under
   the `Reynold4k` account. GitHub will recognize it as the special profile
   repository.
2. Upload every item in this directory, including the hidden `.github`
   directory, while preserving the folder structure.
3. Commit the files to the default branch. The profile README appears at
   `https://github.com/Reynold4k` immediately.
4. Open **Actions → Generate cosmic contribution snake → Run workflow**.
5. If the workflow cannot publish, open **Settings → Actions → General →
   Workflow permissions**, select **Read and write permissions**, save, and run
   it again.

The contribution animation is published to the generated `output` branch.
Everything else works from the first commit.

## Optional command-line publishing

After creating the empty GitHub repository:

```bash
git init
git add .
git commit -m "Create cosmic GitHub profile"
git branch -M main
git remote add origin git@github.com:Reynold4k/Reynold4k.git
git push -u origin main
```

## Customize safely

- Replace `assets/cosmic-hero.png` to change the banner while keeping the same
  filename.
- Edit the factual copy in `README.md`; the layout and visual system can stay
  untouched.
- Keep repository and account capitalization identical so the profile README
  and generated snake URLs resolve correctly.

