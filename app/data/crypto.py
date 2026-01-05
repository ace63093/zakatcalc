"""Top 100 cryptocurrencies for zakat calculation."""

# Top 100 cryptocurrencies by market cap (approximate as of late 2025)
# Format: symbol -> (name, rank)
TOP_100_CRYPTO: dict[str, tuple[str, int]] = {
    'BTC': ('Bitcoin', 1),
    'ETH': ('Ethereum', 2),
    'USDT': ('Tether', 3),
    'BNB': ('BNB', 4),
    'SOL': ('Solana', 5),
    'XRP': ('XRP', 6),
    'USDC': ('USD Coin', 7),
    'ADA': ('Cardano', 8),
    'DOGE': ('Dogecoin', 9),
    'AVAX': ('Avalanche', 10),
    'TRX': ('TRON', 11),
    'DOT': ('Polkadot', 12),
    'LINK': ('Chainlink', 13),
    'MATIC': ('Polygon', 14),
    'TON': ('Toncoin', 15),
    'SHIB': ('Shiba Inu', 16),
    'ICP': ('Internet Computer', 17),
    'DAI': ('Dai', 18),
    'LTC': ('Litecoin', 19),
    'BCH': ('Bitcoin Cash', 20),
    'UNI': ('Uniswap', 21),
    'ATOM': ('Cosmos', 22),
    'ETC': ('Ethereum Classic', 23),
    'XLM': ('Stellar', 24),
    'XMR': ('Monero', 25),
    'OKB': ('OKB', 26),
    'FIL': ('Filecoin', 27),
    'HBAR': ('Hedera', 28),
    'APT': ('Aptos', 29),
    'CRO': ('Cronos', 30),
    'VET': ('VeChain', 31),
    'MKR': ('Maker', 32),
    'NEAR': ('NEAR Protocol', 33),
    'OP': ('Optimism', 34),
    'ARB': ('Arbitrum', 35),
    'GRT': ('The Graph', 36),
    'AAVE': ('Aave', 37),
    'ALGO': ('Algorand', 38),
    'QNT': ('Quant', 39),
    'STX': ('Stacks', 40),
    'EGLD': ('MultiversX', 41),
    'THETA': ('Theta Network', 42),
    'FTM': ('Fantom', 43),
    'AXS': ('Axie Infinity', 44),
    'SAND': ('The Sandbox', 45),
    'EOS': ('EOS', 46),
    'IMX': ('Immutable', 47),
    'MANA': ('Decentraland', 48),
    'XTZ': ('Tezos', 49),
    'RUNE': ('THORChain', 50),
    'KCS': ('KuCoin Token', 51),
    'NEO': ('Neo', 52),
    'FLOW': ('Flow', 53),
    'KLAY': ('Klaytn', 54),
    'CRV': ('Curve DAO', 55),
    'SNX': ('Synthetix', 56),
    'MINA': ('Mina', 57),
    'XEC': ('eCash', 58),
    'CFX': ('Conflux', 59),
    'RPL': ('Rocket Pool', 60),
    'LDO': ('Lido DAO', 61),
    'FXS': ('Frax Share', 62),
    'KAVA': ('Kava', 63),
    'ZEC': ('Zcash', 64),
    'DASH': ('Dash', 65),
    'IOTA': ('IOTA', 66),
    'CHZ': ('Chiliz', 67),
    'PEPE': ('Pepe', 68),
    'SUI': ('Sui', 69),
    'INJ': ('Injective', 70),
    'TIA': ('Celestia', 71),
    'SEI': ('Sei', 72),
    'RENDER': ('Render', 73),
    'FET': ('Fetch.ai', 74),
    'BLUR': ('Blur', 75),
    'WLD': ('Worldcoin', 76),
    'OSMO': ('Osmosis', 77),
    'GMX': ('GMX', 78),
    'CAKE': ('PancakeSwap', 79),
    '1INCH': ('1inch', 80),
    'COMP': ('Compound', 81),
    'BAT': ('Basic Attention Token', 82),
    'ENJ': ('Enjin Coin', 83),
    'ZIL': ('Zilliqa', 84),
    'HOT': ('Holo', 85),
    'ENS': ('Ethereum Name Service', 86),
    'GALA': ('Gala', 87),
    'LRC': ('Loopring', 88),
    'DYDX': ('dYdX', 89),
    'MASK': ('Mask Network', 90),
    'CELO': ('Celo', 91),
    'ONE': ('Harmony', 92),
    'ROSE': ('Oasis Network', 93),
    'ZRX': ('0x', 94),
    'ANKR': ('Ankr', 95),
    'ICX': ('ICON', 96),
    'IOTX': ('IoTeX', 97),
    'SKL': ('SKALE', 98),
    'AUDIO': ('Audius', 99),
    'BAL': ('Balancer', 100),
}


def get_ordered_crypto() -> list[dict]:
    """Get list of cryptocurrencies ordered by rank."""
    result = []
    for symbol, (name, rank) in sorted(TOP_100_CRYPTO.items(), key=lambda x: x[1][1]):
        result.append({
            'symbol': symbol,
            'name': name,
            'rank': rank,
        })
    return result


def get_crypto_symbols() -> list[str]:
    """Get list of crypto symbols in rank order."""
    return [c['symbol'] for c in get_ordered_crypto()]


def is_valid_crypto(symbol: str) -> bool:
    """Check if a crypto symbol is valid."""
    return symbol.upper() in TOP_100_CRYPTO


def get_crypto_info(symbol: str) -> dict | None:
    """Get crypto info by symbol."""
    symbol = symbol.upper()
    if symbol not in TOP_100_CRYPTO:
        return None
    name, rank = TOP_100_CRYPTO[symbol]
    return {
        'symbol': symbol,
        'name': name,
        'rank': rank,
    }
