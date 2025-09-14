# Financial Tracker

A Python-based financial transaction analyzer that processes credit card CSV files, categorizes transactions using rule-based keyword matching, and exports data to PostgreSQL for visualization with Metabase.

## ✨ Features

- **Multi-CSV Support**: Process multiple credit card formats (Citi, Smartly)
- **Rule-Based Categorization**: Transaction categorization using keyword matching with interactive prompts for unknown merchants
- **Configurable Keywords**: YAML-based keyword rules that automatically update when new merchants are categorized
- **PostgreSQL Export**: Direct database export for business intelligence dashboards
- **Metabase Integration**: Pre-built dashboard queries for financial visualization
- **Merchant Name Extraction**: Intelligent cleaning of merchant names from raw transaction data
- **Interactive Prompts**: Manual categorization of unknown transactions with automatic rule learning

## 🚀 Quick Start

1. **Install dependencies**:
   ```bash
   uv sync
   ```

2. **Set up PostgreSQL** (using Docker):
   ```bash
   docker-compose up -d
   ```

3. **Run the analyzer**:
   ```bash
   uv run python financial_analyzer.py
   # Interactive prompts for unknown merchants are enabled by default
   # Categorized transactions are automatically saved to YAML config
   ```

## 📊 Dashboard Setup

The project includes pre-configured Metabase dashboard queries. See `metabase_dashboard_setup.md` for detailed setup instructions.

## 🏷️ Transaction Categorization

The system uses rule-based keyword matching for transaction categorization with interactive prompts for learning new merchants.

### Categories
- **Food**: Restaurants, groceries, coffee shops
- **Shopping**: Retail stores, online shopping, clothing
- **Travel**: Hotels, airlines, gas stations, ride-sharing, parking
- **Utilities**: Phone, internet, electricity, insurance, EV charging
- **Healthcare**: Medical, pharmacy, dental, vision
- **Entertainment**: Movies, gyms, recreation, sports
- **Services**: Professional services, government fees, taxes
- **Payment**: Credit card payments, loan payments, transfers

### How It Works
The system uses a hierarchical approach:
1. **Keyword matching** (checks against categorization_config.yaml)
2. **Interactive prompts** (manual categorization for unknown merchants)
3. **Automatic learning** (saves new keywords to config file)

### Interactive Categorization
When unknown transactions are found:
- **Manual categorization**: Select from 8 predefined categories
- **Automatic learning**: System extracts keywords and saves to config
- **Future matching**: Similar transactions auto-categorize using learned rules
- **Config updates**: Keywords are saved to `categorization_config.yaml`

### Configuration
Transaction categorization uses `categorization_config.yaml`:
- Contains keyword rules for each category
- Automatically updates when new merchants are categorized
- Can be manually edited to add or modify keyword rules

## 🔧 Configuration

### Database Configuration
Database settings are configured in `financial_analyzer.py`:
```python
db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'financial_tracker',
    'user': 'postgres',
    'password': 'postgres'
}
```

### Categorization Configuration
The system uses `categorization_config.yaml` for transaction categorization rules:
- Keywords are automatically learned through interactive prompts
- Rules can be manually edited to add or remove keywords
- No API keys or external services required

## 📁 Project Structure

```
financial-tracker/
├── financial_analyzer.py          # Main analysis script (rule-based approach)
├── categorization_config.yaml     # Keyword-based categorization rules
├── costco_receipts.py             # Costco receipt processing script
├── docker-compose.yml             # PostgreSQL + Metabase setup
├── csv/                           # Directory for CSV files
└── README.md                      # This file
```

## 🧪 Testing

Test the system by running the analyzer with your CSV files:
```bash
uv run python financial_analyzer.py
```

## 📈 Example Output

```
Processing 3 registered CSV files: ['Year to date.CSV', 'costco_transactions.csv', 'Credit Card - 1604_01-01-2025_08-29-2025.csv']
Processing Year to date.CSV with CitiCSVProcessor...
  Processed 245 transactions from Year to date.CSV
Processing costco_transactions.csv with CostcoCSVProcessor...
  Processed 89 transactions from costco_transactions.csv
Using rule-based categorization...
Processed 1,247 transactions

Data successfully exported to PostgreSQL!
You can now connect Metabase to PostgreSQL and create dashboards.

SAMPLE OF PROCESSED DATA
        date description    amount category
0  2025-06-01      COSTCO    234.56     Food
1  2025-06-02        UBER     15.23   Travel
2  2025-06-03   STARBUCKS      8.45     Food
```

All financial analysis and visualization is done through **Metabase dashboards** connected to the PostgreSQL database.

## 🔒 Security

- **Database credentials configurable** per environment
- **No sensitive data logged** or cached permanently
- **CSV files excluded** from version control
- **No external API dependencies** - all processing done locally

## 🛠 Development

### Adding New CSV Formats
Extend the `load_and_process_data()` method in `financial_analyzer.py`.

### Customizing Categories
Update the category lists in the `AVAILABLE_CATEGORIES` constant in `financial_analyzer.py` and add corresponding keyword rules in `categorization_config.yaml`.

## 📄 License

This project is for personal financial tracking and analysis.