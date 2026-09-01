# 🛡️ My Financial Duty & Governance Handbook

> *"Do not save what is left after spending, but spend what is left after saving."* — Warren Buffett  
> *"Rule No. 1: Never lose money. Rule No. 2: Never forget rule No. 1."*

---

## 1. What is `APP_SECRET` & How Authentication Works?

### 🔑 `APP_SECRET` Explained
`APP_SECRET` is the private cryptographic passkey configured in your `.env` file (e.g., `APP_SECRET=Antigravity_Secret_2026`).

- **Local / Personal Dev Mode (Default)**:
  If `APP_SECRET` is empty or `AUTH_DISABLED=true`, Antigravity runs in **Offline Local Mode**. All financial routes work seamlessly without requiring passwords or tokens.
- **Protected Remote Mode**:
  When `APP_SECRET` is set in `.env`, the FastAPI backend (`engine/auth.py`) enforces strict `Bearer` token verification on all `/api/finance/*` and `/api/ai/*` routes.
- **Frontend Auto-Sync (`shared.js`)**:
  When you log in at `/login`, your token is saved in `localStorage`. `shared.js` auto-injects `Authorization: Bearer <APP_SECRET>` on every API call. If a token expires, `shared.js` redirects to `/login`.

---

## 2. My Daily Financial Duty Checklist

| Frequency | Action / Duty | Target Goal | Reward |
| :--- | :--- | :--- | :--- |
| **Daily** | 📝 **Log Every Expense** | Record daily transactions in `/finance` | **+5 XP** |
| **Daily** | 🍛 **Monitor Food & Wants** | Keep daily variable dining under budget | **+10 XP** |
| **Weekly** | 📊 **Review Budget Variance** | Check category health bars (`HEALTHY` vs `WARNING`) | **+25 XP** |
| **Monthly** | 🏦 **Import HDFC Bank Statement** | Upload CSV statement to auto-sync & SHA-256 dedup | **+50 XP** |
| **Monthly** | ⚖️ **Run AI Financial Review** | Evaluate 50/30/20 compliance with Groq AI Advisor | **+100 XP** |

---

## 3. Core Financial Laws & Governance Frameworks

### 1. The 50/30/20 Rule of Wealth Building
Your planned monthly income is divided into 3 mandatory allocation buckets:

- 🏠 **50% Needs & Essential Debt**:
  - Rent, electricity, internet, groceries, phone, mandatory transport, and fixed EMIs.
  - **Rule**: Must not exceed **50%** of net income.
- 🎯 **30% Wants & Lifestyle**:
  - Dining out, coffee, entertainment, shopping, subscriptions.
  - **Rule**: Must not exceed **30%** of net income.
- 💰 **20% Savings & Investments**:
  - Mutual Fund SIPs, Fixed Deposits, Emergency Fund, Equity investments.
  - **Rule**: Must be **≥ 20%** of net income (Pay yourself first on the 1st of every month).

---

### 2. Debt Service Ratio Rule (Target ≤ 20%)
- **Formula**: `(Total Monthly EMIs & Debt Payments / Net Monthly Income) × 100`
- **Governance Limit**:
  - **≤ 20%**: Healthy Debt Level ✅
  - **21% – 35%**: Cautionary Alert ⚠️ (Freeze new debt)
  - **> 35%**: Critical Debt Red Flag 🚨 (Trigger Debt Avalanche / Snowball Method immediately)

---

### 3. Emergency Sinking Fund Rule
- Maintain an **Emergency Sinking Fund** equal to **3 to 6 months of living expenses** (e.g. ₹1,00,000 target).
- Never touch this fund for variable wants or non-emergency shopping.

---

## 4. Smart Bank Statement Routine (Zero Credential Security)

1. **Download Monthly Statement**: Download CSV statement directly from HDFC Bank NetBanking or Paytm/PhonePe export.
2. **Upload to Antigravity**: Open `/finance` → Click **"Import Bank Statement"**.
3. **Auto-Categorization & SHA-256 Dedup**:
   - Antigravity auto-maps descriptions (*Swiggy* → Food, *EMI* → Debt, *Petrol* → Transport).
   - SHA-256 hashing prevents double-importing if the same statement is uploaded twice.
4. **Zero Credential Policy**: Never store NetBanking passwords or PINs.

---

## 5. Antigravity Finance System Quick Links
- **Financial Governance Dashboard**: `/finance`
- **API Health Summary**: `/api/finance/summary`
- **Bank Import API**: `/api/finance/bank_import`
- **AI Financial Coach**: `/api/ai/finance_advisor`
