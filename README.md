# 🏇 TurfAI Pro v5

**Intelligence artificielle pour l'analyse Quinté+ PMU**

TurfAI Pro est un dashboard web qui analyse automatiquement chaque jour
la course Quinté+ PMU grâce à un algorithme IA composite. Il génère les
grilles de paris, détecte les value bets, calcule les mises optimales et
suit tes performances dans le temps.

---

## ✨ Fonctionnalités

- 🤖 **Score IA composite** — 6 critères pondérés par partant
- 💰 **Value Bets** — Détection des cotes sous-évaluées
- 🗂 **Grilles automatiques** — Couplé / Tiercé / Quarté+ / Quinté+
- 🎯 **Bases & Champ** — Construction de sélections personnalisées
- 📊 **Monte Carlo** — 100 000 simulations par course
- 💶 **Kelly Criterion** — Calcul de mises optimales
- 📅 **Historique automatique** — Résultats réels mis à jour en temps réel
- 🤝 **Parrainage** — Partage WhatsApp avec lien unique
- 🔐 **Accès par clé** — Plans Gratuit / PRO / VIP / Admin
- 📱 **Compatible mobile** — Android et iOS

---

## 🚀 Stack technique

| Couche | Technologie |
|--------|------------|
| Frontend | HTML / CSS / JS vanilla (single file) |
| Hébergement | Vercel (déploiement automatique) |
| Backend | Python 3.11 — Railway |
| Scraping | API PMU officielle + Geny.com |
| Paiement | Chariow.com |
| Notifications | CallMeBot WhatsApp |
| CI/CD | GitHub → Vercel auto-deploy |

---

## ⚙️ Pipeline automatique
08h00 → Scraping PMU → Analyse IA → Génère HTML → Push GitHub → WhatsApp
11h00 → Mise à jour des cotes live
16h00 → Scraping résultats → Historique → Push GitHub → WhatsApp
---

## 💳 Plans disponibles

| Plan | Prix | Accès |
|------|------|-------|
| Gratuit | 0€ | Dashboard · Grilles · Historique · Parrainage |
| PRO | 4,90€/mois | + Analyse complète · Value Bets · Kelly · Monte Carlo |
| VIP | 9,90€/mois | + Cotes live · API · Historique 2 ans · Support 2h |

👉 [Boutique Chariow](https://uazgnjsa.mychariow.shop)

---

## 📁 Structure du dépôt
turfai-pro/
├── index.html          ← Dashboard (généré automatiquement chaque jour)
├── historique.json     ← Résultats des 30 derniers jours
├── vercel.json         ← Config Vercel
├── README.md
└── backend/
├── main.py         ← Scheduler automatique
├── scraper.py      ← Scraping API PMU + résultats
├── analyzer.py     ← Algorithme IA composite v5
├── generator.py    ← Génération HTML depuis template
├── github_updater.py ← Push GitHub + gestion historique.json
├── notifier.py     ← Notifications WhatsApp
├── template.html   ← Template de base du dashboard
├── requirements.txt
└── railway.toml
---

## 🌍 Démo live

👉 **[turfai-pro.vercel.app](https://turfai-pro.vercel.app)**

---

> ⚠️ Jeu responsable — 18 ans minimum — [anj.fr](https://anj.fr)# turfai-pro
Dashboard IA d'analyse Quinté+ PMU — Scores composites, Value Bets, Grilles automatiques, Historique et Parrainage
