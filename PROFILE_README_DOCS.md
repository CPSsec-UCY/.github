# CPSEC Organization Profile README

This repository contains the organization profile page for CPSEC-UCY on GitHub.

## Features

### 🎨 Visual Design
- **Hacker-themed ASCII art**: Custom CPSEC-UCY logo in terminal style
- **Animated typing effect**: Dynamic text animation showing the mission
- **Matrix/Terminal aesthetic**: Green-on-black color scheme (#00FF41) reminiscent of classic hacker terminals

### 📊 Dynamic Content
- **Live GitHub Statistics**: Auto-updating organization stats and activity streak
- **Activity Feed**: Automated updates via GitHub Actions (updates every 6 hours)
- **Technology Badges**: Visual representation of tech stack and tools used

### 🔧 Customization

#### Update Featured Projects
Edit the projects table in `/profile/README.md` around lines 75-90 to add/modify featured repositories.

#### Modify Research Areas
Update the research focus areas in `/profile/README.md` around lines 42-75.

#### Change Color Scheme
The primary color is `#00FF41` (matrix green). Search and replace to change:
- Badge colors: `00ff41` in shield.io URLs
- Typing animation: `color=00FF41` parameter
- Stats themes: `title_color`, `icon_color` parameters

### 🤖 Automated Updates

The GitHub Actions workflow (`.github/workflows/update-readme.yml`) automatically updates the activity section:
- **Schedule**: Runs every 6 hours
- **Manual trigger**: Can be run manually via workflow_dispatch
- **On push**: Updates when changes are pushed to main branch

### 📝 External Services Used

1. **readme-typing-svg.demolab.com**: Animated typing effect
2. **github-readme-stats.vercel.app**: Organization statistics
3. **streak-stats.demolab.com**: Contribution streaks
4. **shields.io**: Technology and status badges
5. **capsule-render.vercel.app**: Waving footer banner
6. **visitor-badge.laobi.icu**: Page visitor counter

### 🚀 Deployment

The README in `/profile/README.md` is automatically displayed on the CPSEC-UCY organization homepage when this repository is public.

### 🛠️ Maintenance

1. **Update activity section**: Automatically handled by GitHub Actions
2. **Update projects**: Manually edit the Featured Projects table
3. **Update stats**: No action needed - stats APIs update automatically
4. **Update contact info**: Edit links in the "Collaborate With Us" section

### 📖 Documentation Links

- [GitHub Organization Profile Documentation](https://docs.github.com/en/organizations/collaborating-with-groups-in-organizations/customizing-your-organizations-profile)
- [Markdown Guide](https://www.markdownguide.org/)
- [GitHub Flavored Markdown](https://github.github.com/gfm/)

### 🎯 Best Practices

- Keep the README concise yet informative
- Update featured projects regularly
- Ensure all external links are working
- Test rendering on both light and dark GitHub themes
- Maintain the hacker/security aesthetic consistent with CPSEC brand

---

**Note**: This README is part of a special `.github` repository that provides organization-wide features and profile customization.
