from backend.scanner.unified_market_scanner import UnifiedMarketScanner

scanner = UnifiedMarketScanner()
items = scanner.scan()

print("TYPE OF ITEMS:", type(items))

items = list(items)
print("COUNT:", len(items))

if items:
    first = items[0]
    print("FIRST ITEM TYPE:", type(first))
    print("FIRST ITEM RAW:")
    print(first)

    print("\nDIR / KEYS:")
    if isinstance(first, dict):
        print(first.keys())
    else:
        print(dir(first))