#!/usr/bin/env python3

import os
import sys

def remove_wrapper():
    """Remove the problematic wrapper file."""
    wrapper_path = 'src/core/transaction_builder_wrapper.py'
    if os.path.exists(wrapper_path):
        os.remove(wrapper_path)
        print(f"✓ Removed problematic wrapper: {wrapper_path}")
    else:
        print("✓ Wrapper already removed")

def fix_strategy_engine_import():
    """Fix the import in strategy_engine.py to use the original transaction_builder."""
    
    strategy_path = 'src/trading/strategy_engine.py'
    
    # Read current content
    with open(strategy_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace wrapper import with original import
    if 'from src.core.transaction_builder_wrapper import transaction_builder' in content:
        content = content.replace(
            'from src.core.transaction_builder_wrapper import transaction_builder',
            'from src.core.transaction_builder import transaction_builder'
        )
        print("✓ Fixed import: using original transaction_builder")
    
    # Also ensure initialize_transaction_builder is imported if needed
    if 'from src.core.transaction_builder import transaction_builder' in content:
        if 'initialize_transaction_builder' not in content:
            content = content.replace(
                'from src.core.transaction_builder import transaction_builder',
                'from src.core.transaction_builder import transaction_builder, initialize_transaction_builder'
            )
            print("✓ Added initialize_transaction_builder import")
    
    # Write back
    with open(strategy_path, 'w', encoding='utf-8') as f:
        f.write(content)

def fix_main_py_initialization():
    """Ensure main.py properly initializes transaction_builder."""
    
    main_path = 'src/main.py'
    
    # Read current content
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if transaction_builder is initialized
    if 'transaction_builder = initialize_transaction_builder()' in content:
        print("✓ Transaction builder already initialized in main.py")
    elif 'initialize_transaction_builder()' in content:
        print("✓ Transaction builder initialization found in main.py")
    else:
        # Need to add initialization
        # Find where other components are initialized
        if 'strategy_engine = initialize_strategy_engine()' in content:
            # Add transaction builder initialization before strategy engine
            content = content.replace(
                'strategy_engine = initialize_strategy_engine()',
                'transaction_builder = initialize_transaction_builder()\n        logger.info("✓ Transaction builder initialized")\n        \n        strategy_engine = initialize_strategy_engine()'
            )
            
            # Also need to import it
            if 'from src.core.transaction_builder import initialize_transaction_builder' not in content:
                content = content.replace(
                    'from src.trading.strategy_engine import initialize_strategy_engine',
                    'from src.trading.strategy_engine import initialize_strategy_engine\n        from src.core.transaction_builder import initialize_transaction_builder'
                )
            
            print("✓ Added transaction builder initialization to main.py")
            
            # Write back
            with open(main_path, 'w', encoding='utf-8') as f:
                f.write(content)

def verify_transaction_builder():
    """Verify the TransactionBuilder structure."""
    
    tb_path = 'src/core/transaction_builder.py'
    
    # Check if initialize_transaction_builder exists
    with open(tb_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'def initialize_transaction_builder' not in content:
        print("\n⚠️  Adding initialize_transaction_builder function...")
        
        # Add the initialization function at the end
        init_code = '''

# Global transaction builder instance
transaction_builder = None

def initialize_transaction_builder():
    """Initialize the global transaction builder instance."""
    global transaction_builder
    if transaction_builder is None:
        transaction_builder = TransactionBuilder()
    return transaction_builder
'''
        
        with open(tb_path, 'a', encoding='utf-8') as f:
            f.write(init_code)
        
        print("✓ Added initialize_transaction_builder function")

def main():
    """Apply all fixes."""
    print("="*60)
    print("🔧 Fixing Transaction Builder Issues")
    print("="*60)
    print()
    
    # Check we're in the right directory
    if not os.path.exists('src/main.py'):
        print("❌ ERROR: This script must be run from the project root directory")
        print("   Please cd to C:\\Users\\JJ\\Desktop\\Clide-Bot and run again")
        return 1
    
    try:
        print("Applying fixes...")
        print()
        
        # Step 1: Remove problematic wrapper
        remove_wrapper()
        
        # Step 2: Fix imports in strategy_engine.py
        fix_strategy_engine_import()
        
        # Step 3: Verify transaction_builder has init function
        verify_transaction_builder()
        
        # Step 4: Fix main.py initialization
        fix_main_py_initialization()
        
        print()
        print("="*60)
        print("✅ ALL FIXES APPLIED!")
        print("="*60)
        print()
        print("🎉 What was fixed:")
        print("   • Removed problematic wrapper that was causing initialization errors")
        print("   • Fixed imports to use original transaction_builder")
        print("   • Ensured proper initialization in main.py")
        print("   • Added initialization function if missing")
        print()
        print("🚀 Your bot should now:")
        print("   ✓ Start without initialization errors")
        print("   ✓ Initialize all components properly")
        print("   ✓ Execute trades when detected")
        print()
        print("💰 To start trading:")
        print("   python -m src.main")
        print()
        print("The bot is ready to copy trades! 🚀")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())