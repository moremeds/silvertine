#!/usr/bin/env python3
"""Simple test script to verify ibapi imports work correctly."""

try:
    print("Testing ibapi imports...")
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.order import Order
    print("✓ Basic ibapi imports successful")
    
    try:
        from ibapi.order_cancel import OrderCancel
        print("✓ OrderCancel import successful")
    except ImportError as e:
        print(f"✗ OrderCancel import failed: {e}")
        print("  This may need to be handled differently in newer ibapi versions")
    
    print("\nTesting basic ibapi functionality...")
    
    class TestWrapper(EWrapper):
        pass
        
    class TestClient(EClient):
        def __init__(self, wrapper):
            EClient.__init__(self, wrapper)
    
    wrapper = TestWrapper()
    client = TestClient(wrapper)
    print("✓ Basic client/wrapper creation successful")
    
    # Test contract creation
    contract = Contract()
    contract.symbol = "AAPL"
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    print("✓ Contract creation successful")
    
    # Test order creation
    order = Order()
    order.action = "BUY"
    order.totalQuantity = 100
    order.orderType = "MKT"
    print("✓ Order creation successful")
    
    print("\n🎉 All basic ibapi functionality tests passed!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure ibapi is properly installed")
except Exception as e:
    print(f"❌ Unexpected error: {e}")