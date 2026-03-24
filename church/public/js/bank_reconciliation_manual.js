// Copyright (c) 2023, kunleadenuga and contributors
// User Manual for Bank Reconciliation System

frappe.ui.form.on('Bank Reconciliation', {
    onload: function(frm) {
        // Add User Manual button
        frm.page.add_inner_button(__('📚 User Manual'), function() {
            show_user_manual();
        });
    }
});

function show_user_manual() {
    let d = new frappe.ui.Dialog({
        title: __('📚 Bank Reconciliation - User Manual'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'manual_html',
                options: get_manual_html()
            }
        ]
    });
    
    d.show();
    
    // Add navigation functionality
    d.$wrapper.find('.manual-nav-item').click(function() {
        let section = $(this).data('section');
        d.$wrapper.find('.manual-nav-item').removeClass('active');
        $(this).addClass('active');
        d.$wrapper.find('.manual-section').hide();
        d.$wrapper.find(`#${section}`).show();
        d.$wrapper.find('#manual-content').scrollTop(0);
    });
    
    // Add search functionality
    d.$wrapper.find('#manual-search').on('keyup', function() {
        let search = $(this).val().toLowerCase();
        d.$wrapper.find('.manual-section').each(function() {
            let text = $(this).text().toLowerCase();
            $(this).toggle(text.includes(search));
        });
    });
}

function get_manual_html() {
    return `
        <style>
            .manual-container {
                display: flex;
                height: 600px;
            }
            
            .manual-sidebar {
                width: 250px;
                background: #f8f9fa;
                padding: 20px;
                overflow-y: auto;
                border-right: 2px solid #dee2e6;
            }
            
            .manual-content {
                flex: 1;
                padding: 30px;
                overflow-y: auto;
            }
            
            .manual-nav-item {
                padding: 10px 15px;
                margin-bottom: 5px;
                cursor: pointer;
                border-radius: 5px;
                transition: all 0.2s;
                font-size: 10pt;
            }
            
            .manual-nav-item:hover {
                background: #e9ecef;
            }
            
            .manual-nav-item.active {
                background: #667eea;
                color: white;
                font-weight: 600;
            }
            
            .manual-section {
                margin-bottom: 40px;
            }
            
            .manual-section h2 {
                color: #667eea;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            
            .manual-section h3 {
                color: #495057;
                margin-top: 25px;
                margin-bottom: 15px;
            }
            
            .manual-section h4 {
                color: #6c757d;
                margin-top: 20px;
                margin-bottom: 10px;
            }
            
            .step-box {
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
            }
            
            .step-number {
                display: inline-block;
                width: 30px;
                height: 30px;
                background: #667eea;
                color: white;
                border-radius: 50%;
                text-align: center;
                line-height: 30px;
                font-weight: bold;
                margin-right: 10px;
            }
            
            .info-box {
                background: #d1ecf1;
                border-left: 4px solid #17a2b8;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
            }
            
            .warning-box {
                background: #fff3cd;
                border-left: 4px solid #ffc107;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
            }
            
            .tip-box {
                background: #d4edda;
                border-left: 4px solid #28a745;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
            }
            
            .feature-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin: 20px 0;
            }
            
            .feature-card {
                background: white;
                border: 2px solid #e9ecef;
                padding: 15px;
                border-radius: 8px;
                transition: all 0.2s;
            }
            
            .feature-card:hover {
                border-color: #667eea;
                box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            }
            
            .feature-icon {
                font-size: 24pt;
                margin-bottom: 10px;
            }
            
            code {
                background: #f8f9fa;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                color: #e83e8c;
            }
            
            .shortcut-key {
                display: inline-block;
                background: #343a40;
                color: white;
                padding: 3px 8px;
                border-radius: 3px;
                font-family: monospace;
                font-size: 9pt;
            }
            
            .manual-search {
                width: 100%;
                padding: 10px;
                border: 2px solid #dee2e6;
                border-radius: 5px;
                margin-bottom: 20px;
            }
            
            .screenshot-placeholder {
                background: #e9ecef;
                border: 2px dashed #adb5bd;
                padding: 40px;
                text-align: center;
                color: #6c757d;
                border-radius: 8px;
                margin: 20px 0;
                font-style: italic;
            }
            
            table.manual-table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }
            
            table.manual-table th {
                background: #667eea;
                color: white;
                padding: 10px;
                text-align: left;
            }
            
            table.manual-table td {
                padding: 10px;
                border: 1px solid #dee2e6;
            }
            
            table.manual-table tr:nth-child(even) {
                background: #f8f9fa;
            }
            
            .checklist {
                list-style: none;
                padding-left: 0;
            }
            
            .checklist li {
                padding: 8px 0;
                padding-left: 30px;
                position: relative;
            }
            
            .checklist li:before {
                content: "✓";
                position: absolute;
                left: 0;
                color: #28a745;
                font-weight: bold;
                font-size: 14pt;
            }
        </style>
        
        <div class="manual-container">
            <!-- SIDEBAR NAVIGATION -->
            <div class="manual-sidebar">
                <input type="text" id="manual-search" class="manual-search" placeholder="🔍 Search manual...">
                
                <div class="manual-nav-item active" data-section="section-intro">
                    🏠 Introduction
                </div>
                <div class="manual-nav-item" data-section="section-getting-started">
                    🚀 Getting Started
                </div>
                <div class="manual-nav-item" data-section="section-features">
                    ⭐ Key Features
                </div>
                <div class="manual-nav-item" data-section="section-import">
                    📥 Import Statement
                </div>
                <div class="manual-nav-item" data-section="section-matching">
                    🎯 Transaction Matching
                </div>
                <div class="manual-nav-item" data-section="section-reconciliation">
                    💰 Reconciliation Process
                </div>
                <div class="manual-nav-item" data-section="section-transactions">
                    📝 Creating Transactions
                </div>
                <div class="manual-nav-item" data-section="section-reports">
                    📊 Reports & Printing
                </div>
                <div class="manual-nav-item" data-section="section-best-practices">
                    ⚡ Best Practices
                </div>
                <div class="manual-nav-item" data-section="section-troubleshooting">
                    🔧 Troubleshooting
                </div>
                <div class="manual-nav-item" data-section="section-faq">
                    ❓ FAQ
                </div>
                <div class="manual-nav-item" data-section="section-shortcuts">
                    ⌨️ Keyboard Shortcuts
                </div>
            </div>
            
            <!-- MAIN CONTENT -->
            <div class="manual-content" id="manual-content">
            
                <!-- ============ INTRODUCTION ============ -->
                <div class="manual-section" id="section-intro">
                    <h2>🏠 Introduction</h2>
                    
                    <h3>What is Bank Reconciliation?</h3>
                    <p>
                        Bank Reconciliation is the process of matching the transactions in your company's accounting books 
                        (cashbook) with the transactions that appear on your bank statement. This ensures accuracy and 
                        helps identify any discrepancies.
                    </p>
                    
                    <h3>Why is it Important?</h3>
                    <div class="feature-grid">
                        <div class="feature-card">
                            <div class="feature-icon">✅</div>
                            <h4>Accuracy</h4>
                            <p>Ensures your financial records match bank records</p>
                        </div>
                        <div class="feature-card">
                            <div class="feature-icon">🔍</div>
                            <h4>Error Detection</h4>
                            <p>Identifies mistakes, missing entries, or fraud</p>
                        </div>
                        <div class="feature-card">
                            <div class="feature-icon">💼</div>
                            <h4>Cash Management</h4>
                            <p>Provides accurate cash position for decisions</p>
                        </div>
                        <div class="feature-card">
                            <div class="feature-icon">📈</div>
                            <h4>Audit Compliance</h4>
                            <p>Required for financial audits and reporting</p>
                        </div>
                    </div>
                    
                    <h3>System Overview</h3>
                    <p>
                        This Bank Reconciliation System is a world-class tool that automates and simplifies the 
                        reconciliation process. It includes:
                    </p>
                    <ul class="checklist">
                        <li>Automated bank statement import from CSV/Excel files</li>
                        <li>AI-powered intelligent transaction matching</li>
                        <li>Manual matching capabilities with drag-and-drop interface</li>
                        <li>Automatic creation of adjusting entries</li>
                        <li>Professional reconciliation reports and printing</li>
                        <li>Real-time progress tracking and dashboards</li>
                        <li>Built-in assistant and smart suggestions</li>
                    </ul>
                </div>
                
                <!-- ============ GETTING STARTED ============ -->
                <div class="manual-section" id="section-getting-started" style="display: none;">
                    <h2>🚀 Getting Started</h2>
                    
                    <h3>Creating a New Bank Reconciliation</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Navigate to Bank Reconciliation</strong>
                        <p>Go to: <code>Accounting → Bank Reconciliation → New</code></p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Fill in Basic Details</strong>
                        <ul>
                            <li><strong>Company:</strong> Select your company</li>
                            <li><strong>Bank Account:</strong> Select the bank account to reconcile</li>
                            <li><strong>From Date:</strong> Start date of reconciliation period</li>
                            <li><strong>To Date:</strong> End date of reconciliation period</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Enter Statement Balance</strong>
                        <p>
                            Enter the <strong>Statement Ending Balance</strong> from your bank statement. 
                            This is the closing balance shown on the statement for the period.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">4</span>
                        <strong>Get Bank Entries</strong>
                        <p>
                            Click <code>Actions → 📊 Get Bank Entries</code> to automatically load all 
                            transactions from your GL Entry for the selected period and bank account.
                        </p>
                    </div>
                    
                    <div class="info-box">
                        <strong>💡 Info:</strong> The system will automatically calculate the Cashbook Ending Balance 
                        from your GL Entry records. This should match your Statement Ending Balance after reconciliation.
                    </div>
                    
                    <div class="tip-box">
                        <strong>✨ Tip:</strong> Always reconcile at least monthly. More frequent reconciliations 
                        (weekly or even daily) make the process easier and help catch errors quickly.
                    </div>
                    
                    <h3>Understanding the Dashboard</h3>
                    <p>
                        After loading entries, you'll see a colorful dashboard at the top showing:
                    </p>
                    <ul>
                        <li><strong>Total Entries:</strong> Number of transactions from your books</li>
                        <li><strong>Total Statements:</strong> Number of transactions from bank statement</li>
                        <li><strong>Match Rate:</strong> Percentage of transactions matched</li>
                        <li><strong>Balance Status:</strong> Whether accounts are balanced (✓) or have difference (⚠)</li>
                    </ul>
                    
                    <div class="screenshot-placeholder">
                        📸 Dashboard showing reconciliation progress with colorful cards and progress bars
                    </div>
                </div>
                
                <!-- ============ KEY FEATURES ============ -->
                <div class="manual-section" id="section-features" style="display: none;">
                    <h2>⭐ Key Features</h2>
                    
                    <h3>1. Smart Import</h3>
                    <p>
                        Import bank statements directly from CSV or Excel files with automatic column detection 
                        and preview before import.
                    </p>
                    
                    <h3>2. Intelligent Matching</h3>
                    <p>
                        AI-powered matching engine that uses multiple algorithms:
                    </p>
                    <ul>
                        <li><strong>Amount Matching:</strong> Finds transactions with matching amounts (with tolerance)</li>
                        <li><strong>Date Proximity:</strong> Considers transactions within a date range</li>
                        <li><strong>Fuzzy Party Matching:</strong> Intelligently matches similar party names</li>
                        <li><strong>Cross Matching:</strong> Can match debits with credits and vice versa</li>
                        <li><strong>Confidence Scoring:</strong> Shows how confident the match is (60-100%)</li>
                    </ul>
                    
                    <h3>3. Manual Matching</h3>
                    <p>
                        Drag-and-drop interface for manual matching with real-time search and filtering.
                    </p>
                    
                    <h3>4. Bulk Actions</h3>
                    <p>
                        Check/uncheck multiple transactions at once:
                    </p>
                    <ul>
                        <li>✓ Check All</li>
                        <li>✗ Uncheck All</li>
                        <li>⇄ Invert Selection</li>
                        <li>✓ Check Visible (after filtering)</li>
                    </ul>
                    
                    <h3>5. Quick Filters</h3>
                    <p>
                        Filter transactions instantly:
                    </p>
                    <ul>
                        <li><strong>All:</strong> Show all transactions</li>
                        <li><strong>Matched:</strong> Show only matched items</li>
                        <li><strong>Unmatched:</strong> Show only unmatched items</li>
                        <li><strong>Debit Only:</strong> Show only debit transactions</li>
                        <li><strong>Credit Only:</strong> Show only credit transactions</li>
                        <li><strong>Search:</strong> Free text search across all fields</li>
                    </ul>
                    
                    <h3>6. Progress Tracking</h3>
                    <p>
                        Real-time visual progress bars showing:
                    </p>
                    <ul>
                        <li>Overall progress percentage</li>
                        <li>Bank entries matched vs unmatched</li>
                        <li>Bank statements matched vs unmatched</li>
                        <li>Celebration message when 100% complete! 🎉</li>
                    </ul>
                    
                    <h3>7. Smart Suggestions</h3>
                    <p>
                        AI assistant provides intelligent suggestions:
                    </p>
                    <ul>
                        <li>Alerts for large unmatched transactions</li>
                        <li>Warnings for old unmatched items (>30 days)</li>
                        <li>Duplicate detection</li>
                        <li>Low match rate alerts</li>
                        <li>Balance mismatch notifications</li>
                    </ul>
                    
                    <h3>8. Reconciliation Assistant (Chatbot)</h3>
                    <p>
                        Interactive chatbot that answers questions like:
                    </p>
                    <ul>
                        <li>"How many transactions are unmatched?"</li>
                        <li>"What's my balance status?"</li>
                        <li>"Show me my progress"</li>
                        <li>"How do I match transactions?"</li>
                    </ul>
                    
                    <h3>9. Duplicate Detection</h3>
                    <p>
                        Automatically finds potential duplicate entries and allows you to remove them with one click.
                    </p>
                    
                    <h3>10. Professional Reports</h3>
                    <p>
                        Generate beautifully formatted reconciliation statements with:
                    </p>
                    <ul>
                        <li>Executive summary on page 1</li>
                        <li>Detailed transaction listings</li>
                        <li>Reconciling items breakdown</li>
                        <li>Professional formatting for board presentations</li>
                    </ul>
                </div>
                
                <!-- ============ IMPORT STATEMENT ============ -->
                <div class="manual-section" id="section-import" style="display: none;">
                    <h2>📥 Import Bank Statement</h2>
                    
                    <h3>Preparing Your Bank Statement File</h3>
                    
                    <div class="info-box">
                        <strong>✅ Supported Formats:</strong>
                        <ul>
                            <li>CSV (.csv)</li>
                            <li>Excel (.xlsx, .xls)</li>
                        </ul>
                    </div>
                    
                    <div class="warning-box">
                        <strong>⚠️ Before Importing:</strong>
                        <ul>
                            <li>Download statement from your online banking</li>
                            <li>Ensure dates are in a recognized format (DD/MM/YYYY or MM/DD/YYYY)</li>
                            <li>Remove any header rows or footer totals (optional - system can handle headers)</li>
                            <li>Save as CSV or Excel format</li>
                        </ul>
                    </div>
                    
                    <h3>Step-by-Step Import Process</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Open Import Dialog</strong>
                        <p>Click <code>Actions → 📥 Import Statement</code></p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Upload File</strong>
                        <p>
                            Click <strong>Choose File</strong> and select your bank statement file. 
                            The system will automatically preview the file.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Preview Data</strong>
                        <p>
                            You'll see a table showing the first 10 rows of your file. Review to ensure 
                            the file was read correctly.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">4</span>
                        <strong>Map Columns</strong>
                        <p>
                            The system auto-detects columns, but verify:
                        </p>
                        <ul>
                            <li><strong>Date Column:</strong> Select column containing transaction dates</li>
                            <li><strong>Party/Description:</strong> Column with payee/description</li>
                            <li><strong>Debit Column:</strong> Column with debit/withdrawal amounts</li>
                            <li><strong>Credit Column:</strong> Column with credit/deposit amounts</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">5</span>
                        <strong>Configure Options</strong>
                        <ul>
                            <li><strong>Header Row Number:</strong> Usually 1 (first row contains headers)</li>
                            <li><strong>Clear Existing Statements:</strong> Check to remove old data before import</li>
                            <li><strong>Skip Duplicates:</strong> Check to avoid importing duplicate transactions</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">6</span>
                        <strong>Click Import</strong>
                        <p>
                            Click the <strong>Import</strong> button. You'll see a progress message and 
                            confirmation of how many transactions were imported.
                        </p>
                    </div>
                    
                    <div class="tip-box">
                        <strong>💡 Pro Tip:</strong> The system remembers your column mappings! Next time you 
                        import from the same bank, it will auto-select the correct columns.
                    </div>
                    
                    <h3>Common Import Issues & Solutions</h3>
                    
                    <table class="manual-table">
                        <thead>
                            <tr>
                                <th>Issue</th>
                                <th>Solution</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Dates not recognized</td>
                                <td>Ensure dates are in DD/MM/YYYY or MM/DD/YYYY format in your file</td>
                            </tr>
                            <tr>
                                <td>Amounts importing as text</td>
                                <td>Remove currency symbols (₦, $) from the file before import</td>
                            </tr>
                            <tr>
                                <td>Some rows skipped</td>
                                <td>Check for blank rows or missing required data (date, amount)</td>
                            </tr>
                            <tr>
                                <td>Wrong columns detected</td>
                                <td>Manually select correct columns from dropdowns</td>
                            </tr>
                            <tr>
                                <td>Import button disabled</td>
                                <td>Ensure Date Column is selected (it's required)</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- ============ TRANSACTION MATCHING ============ -->
                <div class="manual-section" id="section-matching" style="display: none;">
                    <h2>🎯 Transaction Matching</h2>
                    
                    <h3>Understanding Matching</h3>
                    <p>
                        Matching is the process of finding which transactions in your books correspond to 
                        transactions on the bank statement. Once matched, these items are marked as reconciled (✓).
                    </p>
                    
                    <h3>Automatic Intelligent Matching</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Open Matching Dialog</strong>
                        <p>Click the <code>Match</code> button or press <span class="shortcut-key">Ctrl+M</span></p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Configure Matching Parameters</strong>
                        
                        <h4>Amount Tolerance</h4>
                        <p>
                            Maximum difference in amounts to consider a match. Default: 1.00<br>
                            <em>Example: If set to 1.00, transactions of ₦1000.00 and ₦1000.50 can match</em>
                        </p>
                        
                        <h4>Date Range (±days)</h4>
                        <p>
                            How many days before/after to search for matches. Default: 5 days<br>
                            <em>Example: A payment on Jan 5 can match statements from Jan 1-10</em>
                        </p>
                        
                        <h4>Enable Cross Matching</h4>
                        <p>
                            When checked, can match debit in books with credit in statement (and vice versa).<br>
                            <em>Useful when bank records withdrawals as credits</em>
                        </p>
                        
                        <h4>Fuzzy Party Name Matching</h4>
                        <p>
                            Uses AI to match similar but not identical party names.<br>
                            <em>Example: "ABC Limited" matches "ABC Ltd"</em>
                        </p>
                        
                        <h4>Minimum Confidence (%)</h4>
                        <p>
                            Only show matches with this confidence level or higher. Default: 60%<br>
                            <em>Lower = more suggestions, Higher = fewer but more accurate</em>
                        </p>
                        
                        <h4>Auto-match High Confidence (>90%)</h4>
                        <p>
                            Automatically mark matches above 90% confidence without review.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Start Matching</strong>
                        <p>Click <strong>Start Matching</strong>. The system will analyze all transactions.</p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">4</span>
                        <strong>Review Results</strong>
                        <p>You'll see a summary table showing:</p>
                        <ul>
                            <li><strong>✓ Auto-Matched:</strong> High confidence matches (already marked as reconciled)</li>
                            <li><strong>⚡ Suggested for Review:</strong> Medium confidence matches (review before accepting)</li>
                            <li><strong>⚠ Unmatched:</strong> No good matches found</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">5</span>
                        <strong>Review Suggested Matches</strong>
                        <p>
                            For each suggested match, you'll see:
                        </p>
                        <ul>
                            <li>Bank entry details (left side)</li>
                            <li>Confidence percentage badge (center)</li>
                            <li>Match type description</li>
                            <li>Bank statement details (right side)</li>
                            <li>Checkbox to accept the match</li>
                        </ul>
                    </div>
                    
                    <div class="info-box">
                        <strong>🎨 Confidence Color Coding:</strong>
                        <ul>
                            <li><span style="background: #d4edda; padding: 2px 8px; border-radius: 3px;">Green (80-100%)</span> - High confidence, likely correct</li>
                            <li><span style="background: #fff3cd; padding: 2px 8px; border-radius: 3px;">Yellow (60-79%)</span> - Medium confidence, review carefully</li>
                            <li><span style="background: #f8d7da; padding: 2px 8px; border-radius: 3px;">Red (<60%)</span> - Low confidence, verify thoroughly</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">6</span>
                        <strong>Apply Selected Matches</strong>
                        <p>
                            Check the boxes for matches you want to accept (high confidence matches are 
                            pre-checked), then click <strong>Apply Selected Matches</strong>.
                        </p>
                    </div>
                    
                    <div class="tip-box">
                        <strong>✨ Best Practice:</strong> Always review matches before accepting, especially 
                        those below 90% confidence. Click the "Details" button to see a detailed comparison.
                    </div>
                    
                    <h3>Manual Matching</h3>
                    
                    <p>For transactions that couldn't be automatically matched, use manual matching:</p>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Open Manual Match Dialog</strong>
                        <p>Click <code>Actions → 🔗 Manual Match</code></p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Select Transactions</strong>
                        <p>
                            You'll see two columns:
                        </p>
                        <ul>
                            <li><strong>Left:</strong> Bank Entries (from your books)</li>
                            <li><strong>Right:</strong> Bank Statements (from bank)</li>
                        </ul>
                        <p>Click one transaction from each side to select them.</p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Match Them</strong>
                        <p>
                            Click the <strong>Match →</strong> button in the center. The matched pair will 
                            appear at the bottom and disappear from the selection lists.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">4</span>
                        <strong>Continue Matching</strong>
                        <p>Repeat for other transactions. Use the search boxes to filter large lists.</p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">5</span>
                        <strong>Save Matches</strong>
                        <p>Click <strong>Save Matches</strong> when done. All matched transactions will be marked as reconciled.</p>
                    </div>
                    
                    <div class="tip-box">
                        <strong>💡 Search Tip:</strong> Use the search boxes at the top of each column to quickly 
                        find specific transactions by party name, amount, or date.
                    </div>
                    
                    <h3>Match Type Explanations</h3>
                    
                    <table class="manual-table">
                        <thead>
                            <tr>
                                <th>Match Type</th>
                                <th>Explanation</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Direct Debit Match</td>
                                <td>Debit in books matches debit in statement (withdrawal/payment)</td>
                            </tr>
                            <tr>
                                <td>Direct Credit Match</td>
                                <td>Credit in books matches credit in statement (deposit/receipt)</td>
                            </tr>
                            <tr>
                                <td>Cross Match (Debit ↔ Credit)</td>
                                <td>Debit in books matches credit in statement (reversed recording)</td>
                            </tr>
                            <tr>
                                <td>Cross Match (Credit ↔ Debit)</td>
                                <td>Credit in books matches debit in statement (reversed recording)</td>
                            </tr>
                            <tr>
                                <td>Amount Match</td>
                                <td>Amounts match but other factors differ slightly</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- ============ RECONCILIATION PROCESS ============ -->
                <div class="manual-section" id="section-reconciliation" style="display: none;">
                    <h2>💰 Complete Reconciliation Process</h2>
                    
                    <h3>Understanding Reconciling Items</h3>
                    
                    <p>
                        Even after matching, your Statement Balance and Cashbook Balance might not match. 
                        This is normal! The difference is explained by <strong>Reconciling Items</strong>:
                    </p>
                    
                    <h4>1. Unpresented Cheques / Payments</h4>
                    <p>
                        <strong>What:</strong> Cheques you've issued (recorded in books) but haven't been cashed by recipients yet.<br>
                        <strong>Effect:</strong> Reduces your bank balance but not yet on statement<br>
                        <strong>Example:</strong> You wrote a cheque on Jan 28, but it was cashed on Feb 3
                    </p>
                    
                    <h4>2. Uncredited Cheques / Deposits</h4>
                    <p>
                        <strong>What:</strong> Cheques/deposits you've recorded but bank hasn't processed yet.<br>
                        <strong>Effect:</strong> Increases your bank balance but not yet on statement<br>
                        <strong>Example:</strong> Deposit made on Jan 31 (Friday) appears on statement Feb 3 (Monday)
                    </p>
                    
                    <h4>3. Direct Withdrawals</h4>
                    <p>
                        <strong>What:</strong> Bank charges, fees, or withdrawals not yet recorded in your books.<br>
                        <strong>Effect:</strong> On bank statement but not in your books<br>
                        <strong>Examples:</strong> Bank charges, ATM fees, loan repayments, standing orders
                    </p>
                    
                    <h4>4. Direct Lodgments</h4>
                    <p>
                        <strong>What:</strong> Interest, deposits, or receipts on bank statement but not in your books.<br>
                        <strong>Effect:</strong> On bank statement but not in your books<br>
                        <strong>Examples:</strong> Interest income, direct deposits from customers, refunds
                    </p>
                    
                    <h3>Identifying Reconciling Items</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Get Unpresented Cheques</strong>
                        <p>
                            Click the <code>Get Unpre</code> button. This automatically copies all unreconciled 
                            CREDIT transactions from Bank Entries to the Unpresented Cheques table.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Get Uncredited Cheques</strong>
                        <p>
                            Click the <code>Get Uncre</code> button. This automatically copies all unreconciled 
                            DEBIT transactions from Bank Entries to the Uncredited Cheques table.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Get Direct Withdrawals</strong>
                        <p>
                            Click the <code>Get DW</code> button. This automatically copies all unreconciled 
                            DEBIT transactions from Bank Statement to the Direct Withdrawals table.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">4</span>
                        <strong>Get Direct Lodgments</strong>
                        <p>
                            Click the <code>Get DL</code> button. This automatically copies all unreconciled 
                            CREDIT transactions from Bank Statement to the Direct Lodgments table.
                        </p>
                    </div>
                    
                    <div class="info-box">
                        <strong>💡 Smart Feature:</strong> The system prevents duplicates! If you click these 
                        buttons multiple times, existing entries won't be duplicated.
                    </div>
                    
                    <h3>Review Reconciling Items</h3>
                    
                    <p>After getting reconciling items, review each table:</p>
                    
                    <ul>
                        <li>Verify all entries are correct</li>
                        <li>Remove any that don't belong</li>
                        <li>Add manual entries if needed (using the + Add Row button)</li>
                    </ul>
                    
                    <h3>Understanding the Reconciliation Formula</h3>
                    
                    <div class="info-box">
                        <strong>📐 Reconciliation Formula:</strong>
                        <p style="font-family: monospace; background: white; padding: 10px; margin-top: 10px; border-radius: 5px;">
                            Statement Balance<br>
                            + Unpresented Cheques<br>
                            - Uncredited Cheques<br>
                            + Direct Withdrawals<br>
                            - Direct Lodgments<br>
                            = Calculated Cash Book Balance<br>
                        </p>
                        <p>
                            If <strong>Calculated Balance = Actual Cashbook Balance</strong>, you're balanced! ✓
                        </p>
                    </div>
                    
                    <h3>Achieving Balance</h3>
                    
                    <p>Check the <strong>Balance Diff</strong> field:</p>
                    
                    <ul>
                        <li><strong>₦0.00 (NIL):</strong> 🎉 Perfect! You're balanced.</li>
                        <li><strong>Small amount (< ₦1):</strong> Likely rounding difference - acceptable</li>
                        <li><strong>Larger amount:</strong> Review for missing reconciling items</li>
                    </ul>
                    
                    <div class="tip-box">
                        <strong>✨ Troubleshooting Balance Differences:</strong>
                        <ul>
                            <li>Re-check your Statement Ending Balance entry</li>
                            <li>Verify all reconciling items are captured</li>
                            <li>Look for unmatched transactions</li>
                            <li>Check for duplicate entries (use <code>🔍 Check Duplicates</code>)</li>
                            <li>Use the <code>🤖 Assistant</code> for guidance</li>
                        </ul>
                    </div>
                    
                    <h3>Save & Finalize</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Save Document</strong>
                        <p>Click <strong>Save</strong>. The system calculates all totals and status automatically.</p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Review Status</strong>
                        <p>
                            The <strong>Status</strong> field will show:
                        </p>
                        <ul>
                            <li><strong>Reconciled:</strong> Balance difference is NIL</li>
                            <li><strong>Not Reconciled:</strong> Balance difference exists</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Submit (Optional)</strong>
                        <p>Once satisfied, click <strong>Submit</strong> to finalize the reconciliation.</p>
                    </div>
                    
                    <div class="warning-box">
                        <strong>⚠️ Before Submitting:</strong>
                        <ul>
                            <li>Ensure balance difference is NIL or acceptable</li>
                            <li>All reconciling items are correctly classified</li>
                            <li>Direct withdrawals/lodgments have been recorded (see next section)</li>
                            <li>Print/export the report for your records</li>
                        </ul>
                    </div>
                </div>
                
                <!-- ============ CREATING TRANSACTIONS ============ -->
                <div class="manual-section" id="section-transactions" style="display: none;">
                    <h2>📝 Creating Transactions</h2>
                    
                    <h3>Why Create Transactions?</h3>
                    
                    <p>
                        Direct Withdrawals and Direct Lodgments represent transactions that appeared on your 
                        bank statement but weren't in your books. You need to record these to update your 
                        accounting records.
                    </p>
                    
                    <h3>Automatic Transaction Creation</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Review Items</strong>
                        <p>
                            Before creating, review your Direct Withdrawals and Direct Lodgments tables. 
                            Ensure all entries are correct and properly categorized.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Click Create Entries</strong>
                        <p>
                            Click <code>Actions → 💰 Create Entries</code>
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Confirm Action</strong>
                        <p>
                            A confirmation dialog will appear. Click <strong>Yes</strong> to proceed.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">4</span>
                        <strong>System Creates Transactions</strong>
                        <p>
                            The system automatically creates:
                        </p>
                        <ul>
                            <li><strong>Payments</strong> for each Direct Withdrawal</li>
                            <li><strong>Receipts</strong> for each Direct Lodgment</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">5</span>
                        <strong>Review Created Transactions</strong>
                        <p>
                            You'll see success messages showing how many Payments and Receipts were created. 
                            The transactions are created in <strong>Draft</strong> status for your review.
                        </p>
                    </div>
                    
                    <div class="info-box">
                        <strong>✅ What the System Does:</strong>
                        <ul>
                            <li>Checks for duplicates (won't create if transaction already exists)</li>
                            <li>Populates all required fields automatically</li>
                            <li>Uses correct account, currency, and company settings</li>
                            <li>Creates transactions in Draft for your review</li>
                            <li>Shows clear success/skip/error messages</li>
                        </ul>
                    </div>
                    
                    <h3>Transaction Details</h3>
                    
                    <h4>Payments Created (From Direct Withdrawals)</h4>
                    <ul>
                        <li><strong>Type:</strong> Expense Payment</li>
                        <li><strong>Payee:</strong> From party field (or "Bank Charges" if blank)</li>
                        <li><strong>Amount:</strong> From debit amount</li>
                        <li><strong>Bank:</strong> Your reconciliation bank account</li>
                        <li><strong>Purpose:</strong> From remarks or "Direct Withdrawal from Bank Reconciliation"</li>
                        <li><strong>Reference:</strong> Cheque number or auto-generated reference</li>
                    </ul>
                    
                    <h4>Receipts Created (From Direct Lodgments)</h4>
                    <ul>
                        <li><strong>Type:</strong> Receive from Registered</li>
                        <li><strong>Customer:</strong> From party field (or "Direct Lodgment" if blank)</li>
                        <li><strong>Amount:</strong> From credit amount</li>
                        <li><strong>Bank:</strong> Your reconciliation bank account</li>
                        <li><strong>Purpose:</strong> From remarks or "Direct Lodgment from Bank Reconciliation"</li>
                        <li><strong>Reference:</strong> Cheque number or auto-generated reference</li>
                    </ul>
                    
                    <h3>After Creation</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Review Created Transactions</strong>
                        <p>
                            Navigate to:
                        </p>
                        <ul>
                            <li><code>Payments</code> list to review created payments</li>
                            <li><code>Receipts</code> list to review created receipts</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Edit if Needed</strong>
                        <p>
                            Since transactions are in Draft, you can:
                        </p>
                        <ul>
                            <li>Update account classifications</li>
                            <li>Add cost centers</li>
                            <li>Adjust descriptions</li>
                            <li>Add additional information</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Submit Transactions</strong>
                        <p>
                            After reviewing, submit each transaction to post to GL Entry.
                        </p>
                    </div>
                    
                    <div class="tip-box">
                        <strong>💡 Best Practice:</strong> Always review created transactions before submitting. 
                        Ensure accounts, cost centers, and other details are correct for your accounting standards.
                    </div>
                    
                    <h3>Duplicate Prevention</h3>
                    
                    <p>
                        The system prevents duplicate transaction creation:
                    </p>
                    
                    <ul>
                        <li>Checks by: Date + Amount + Reference + Company</li>
                        <li>If duplicate found, shows orange alert and skips</li>
                        <li>You can safely click "Create Entries" multiple times</li>
                        <li>Summary shows: Created, Skipped, and Errors</li>
                    </ul>
                    
                    <div class="info-box">
                        <strong>🎯 Example Summary:</strong>
                        <div style="background: white; padding: 10px; margin-top: 10px; border-radius: 5px;">
                            ✓ Created 5 Payment(s)<br>
                            ⊘ Skipped 2 duplicate Payment(s)<br>
                            ✓ Created 3 Receipt(s)<br>
                            ⊘ Skipped 1 duplicate Receipt(s)
                        </div>
                    </div>
                </div>
                
                <!-- ============ REPORTS & PRINTING ============ -->
                <div class="manual-section" id="section-reports" style="display: none;">
                    <h2>📊 Reports & Printing</h2>
                    
                    <h3>Printing Reconciliation Statement</h3>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Click Print Statement</strong>
                        <p>
                            Click <code>Actions → 🖨️ Print Statement</code> or press <span class="shortcut-key">Ctrl+P</span>
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Review Print Preview</strong>
                        <p>
                            The professional print format opens in a new window/tab with:
                        </p>
                        <ul>
                            <li><strong>Page 1:</strong> Executive Summary & Reconciliation Summary</li>
                            <li><strong>Page 2+:</strong> Detailed transaction listings</li>
                        </ul>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Print or Save as PDF</strong>
                        <p>
                            Use your browser's print function:
                        </p>
                        <ul>
                            <li>To Print: Select printer and click Print</li>
                            <li>To Save as PDF: Select "Save as PDF" as destination</li>
                        </ul>
                    </div>
                    
                    <h3>Print Format Features</h3>
                    
                    <h4>Page 1 - Executive Summary</h4>
                    <ul>
                        <li>Company header with bank account details</li>
                        <li>Reconciliation period and status</li>
                        <li>Four summary cards showing key balances</li>
                        <li>Reconciliation summary with calculation breakdown</li>
                        <li>Narration/notes section</li>
                    </ul>
                    
                    <h4>Page 2+ - Transaction Details</h4>
                    <ul>
                        <li>Bank Account Entries (all transactions with match status)</li>
                        <li>Unpresented Cheques/Payments</li>
                        <li>Uncredited Cheques/Deposits</li>
                        <li>Direct Withdrawals</li>
                        <li>Direct Lodgments</li>
                        <li>Signature section (Prepared, Reviewed, Approved)</li>
                        <li>Generation timestamp and reference</li>
                    </ul>
                    
                    <div class="tip-box">
                        <strong>💡 Professional Tip:</strong> The print format is designed for board presentations 
                        and audit requirements. Page 1 gives executives a quick overview, while subsequent pages 
                        provide auditors with detailed transaction support.
                    </div>
                    
                    <h3>Exporting Unmatched Transactions</h3>
                    
                    <p>Export unmatched items to CSV for further analysis:</p>
                    
                    <div class="step-box">
                        <span class="step-number">1</span>
                        <strong>Click Export Unmatched</strong>
                        <p>
                            Click <code>Actions → 📤 Export Unmatched</code>
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">2</span>
                        <strong>Download CSV</strong>
                        <p>
                            A CSV file downloads automatically containing all unmatched transactions from 
                            both Bank Entries and Bank Statements.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <span class="step-number">3</span>
                        <strong>Open in Excel</strong>
                        <p>
                            Open the CSV file in Excel or Google Sheets for analysis, sharing with team, 
                            or investigation.
                        </p>
                    </div>
                    
                    <h3>Generate Reports</h3>
                    
                    <p>
                        Click <code>Actions → 📄 Generate Report</code> to access the Bank Reconciliation 
                        Query Report with advanced filtering and analysis options.
                    </p>
                </div>
                
                <!-- ============ BEST PRACTICES ============ -->
                <div class="manual-section" id="section-best-practices" style="display: none;">
                    <h2>⚡ Best Practices</h2>
                    
                    <h3>Frequency</h3>
                    <ul class="checklist">
                        <li>Reconcile at least monthly (required for most businesses)</li>
                        <li>Weekly reconciliation recommended for high-volume accounts</li>
                        <li>Daily reconciliation ideal for critical accounts</li>
                        <li>Don't wait until year-end - errors are harder to find</li>
                    </ul>
                    
                    <h3>Before You Start</h3>
                    <ul class="checklist">
                        <li>Ensure all transactions are posted in your accounting system</li>
                        <li>Download latest bank statement</li>
                        <li>Have previous reconciliation handy for reference</li>
                        <li>Block 30-60 minutes of uninterrupted time</li>
                    </ul>
                    
                    <h3>During Reconciliation</h3>
                    <ul class="checklist">
                        <li>Start with auto-matching to handle majority quickly</li>
                        <li>Review suggested matches carefully (don't blindly accept)</li>
                        <li>Use manual matching for remaining items</li>
                        <li>Investigate large unmatched transactions immediately</li>
                        <li>Don't ignore small differences - they can indicate bigger issues</li>
                    </ul>
                    
                    <h3>Reconciling Items</h3>
                    <ul class="checklist">
                        <li>Review unpresented cheques - investigate any over 30 days old</li>
                        <li>Verify uncredited deposits clear within 2-3 business days</li>
                        <li>Always record bank charges and interest immediately</li>
                        <li>Investigate any unusual direct debits/credits</li>
                    </ul>
                    
                    <h3>Quality Control</h3>
                    <ul class="checklist">
                        <li>Use the Duplicate Checker regularly</li>
                        <li>Review Smart Suggestions for anomalies</li>
                        <li>Check Progress Tracker - aim for 95%+ match rate</li>
                        <li>Print reconciliation statement for records</li>
                        <li>Have someone else review before finalizing</li>
                    </ul>
                    
                    <h3>Documentation</h3>
                    <ul class="checklist">
                        <li>Add narration explaining unusual items or adjustments</li>
                        <li>Keep copies of bank statements</li>
                        <li>Save printed reconciliation reports</li>
                        <li>Document investigation of discrepancies</li>
                        <li>Maintain reconciliation file by period</li>
                    </ul>
                    
                    <h3>Security</h3>
                    <ul class="checklist">
                        <li>Ensure only authorized staff perform reconciliation</li>
                        <li>Segregate duties - different person should review</li>
                        <li>Submit reconciliation only after thorough review</li>
                        <li>Report suspicious transactions immediately</li>
                    </ul>
                    
                    <div class="tip-box">
                        <strong>🌟 Pro Tip:</strong> Create a reconciliation checklist specific to your organization 
                        and follow it every time. Consistency reduces errors and saves time.
                    </div>
                    
                    <h3>Common Mistakes to Avoid</h3>
                    
                    <table class="manual-table">
                        <thead>
                            <tr>
                                <th>Mistake</th>
                                <th>Why It's Bad</th>
                                <th>How to Avoid</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Reconciling infrequently</td>
                                <td>Errors accumulate and are harder to find</td>
                                <td>Set a regular schedule (monthly minimum)</td>
                            </tr>
                            <tr>
                                <td>Ignoring small differences</td>
                                <td>Small errors can indicate larger problems</td>
                                <td>Investigate all differences, no matter how small</td>
                            </tr>
                            <tr>
                                <td>Not reviewing auto-matches</td>
                                <td>System might match incorrectly sometimes</td>
                                <td>Always review, especially <90% confidence</td>
                            </tr>
                            <tr>
                                <td>Forcing balance</td>
                                <td>Hides real accounting errors</td>
                                <td>Find and fix root cause, don't adjust to match</td>
                            </tr>
                            <tr>
                                <td>Not documenting issues</td>
                                <td>Can't remember or prove later</td>
                                <td>Use narration field, keep notes</td>
                            </tr>
                            <tr>
                                <td>Duplicating entries</td>
                                <td>Overstates transactions</td>
                                <td>Use Duplicate Checker regularly</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- ============ TROUBLESHOOTING ============ -->
                <div class="manual-section" id="section-troubleshooting" style="display: none;">
                    <h2>🔧 Troubleshooting</h2>
                    
                    <h3>Balance Won't Reconcile</h3>
                    
                    <h4>Issue: Large Balance Difference</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Verify Statement Ending Balance is entered correctly</li>
                            <li>Check if all GL entries were loaded (click Get Bank Entries again)</li>
                            <li>Look for large unmatched transactions</li>
                            <li>Use Duplicate Checker - might have duplicate entries</li>
                            <li>Verify reconciling items are in correct tables</li>
                            <li>Check for transactions in wrong period</li>
                        </ul>
                    </div>
                    
                    <h4>Issue: Small Persistent Difference (e.g., ₦0.05)</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Usually rounding differences - acceptable if <₦1</li>
                            <li>Check if using correct decimal places</li>
                            <li>Verify exchange rates if multi-currency</li>
                        </ul>
                    </div>
                    
                    <h3>Import Issues</h3>
                    
                    <h4>Issue: File Won't Upload</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Check file format (must be CSV or Excel)</li>
                            <li>Ensure file isn't corrupted (try opening in Excel first)</li>
                            <li>File size might be too large - try splitting</li>
                            <li>Check internet connection</li>
                        </ul>
                    </div>
                    
                    <h4>Issue: Wrong Data Imported</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Clear imported data: Actions → Clear Tables</li>
                            <li>Re-import with correct column mappings</li>
                            <li>Check Header Row Number setting</li>
                            <li>Verify file has proper format (dates, numbers)</li>
                        </ul>
                    </div>
                    
                    <h4>Issue: Dates Not Importing Correctly</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Format dates as DD/MM/YYYY or MM/DD/YYYY in source file</li>
                            <li>Don't use text dates (like "Jan 5, 2024")</li>
                            <li>Remove any date formatting from Excel (use Text format)</li>
                        </ul>
                    </div>
                    
                    <h3>Matching Issues</h3>
                    
                    <h4>Issue: No Matches Found</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Increase Amount Tolerance (try 5.00 or 10.00)</li>
                            <li>Increase Date Range (try 10-15 days)</li>
                            <li>Enable Cross Matching</li>
                            <li>Lower Minimum Confidence to 50%</li>
                            <li>Enable Fuzzy Party Matching</li>
                            <li>Some transactions may need manual matching</li>
                        </ul>
                    </div>
                    
                    <h4>Issue: Too Many False Matches</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Decrease Amount Tolerance (try 0.50 or 1.00)</li>
                            <li>Decrease Date Range (try 2-3 days)</li>
                            <li>Increase Minimum Confidence to 70-80%</li>
                            <li>Disable Auto-match High Confidence - review all</li>
                            <li>Always review suggested matches before accepting</li>
                        </ul>
                    </div>
                    
                    <h3>Performance Issues</h3>
                    
                    <h4>Issue: System Running Slow</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Clear browser cache and refresh</li>
                            <li>Close other browser tabs</li>
                            <li>For large datasets (>1000 transactions), consider splitting by week</li>
                            <li>Use filters to work with smaller subsets</li>
                            <li>Clear unused tables regularly</li>
                        </ul>
                    </div>
                    
                    <h3>Transaction Creation Issues</h3>
                    
                    <h4>Issue: Error Creating Transactions</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Check error message - usually indicates missing required field</li>
                            <li>Ensure party names are valid</li>
                            <li>Verify cost center exists</li>
                            <li>Check user permissions for creating Payments/Receipts</li>
                            <li>Review error log: Tools → Error Log</li>
                        </ul>
                    </div>
                    
                    <h4>Issue: Transactions Created but Not Showing in GL</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Transactions are created in Draft - you must Submit them</li>
                            <li>Navigate to Payments/Receipts list</li>
                            <li>Open each transaction and click Submit</li>
                            <li>Check if accounting entries creation is enabled in transaction</li>
                        </ul>
                    </div>
                    
                    <h3>General Issues</h3>
                    
                    <h4>Issue: Can't Save Document</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Check required fields are filled (red asterisks)</li>
                            <li>Look for error messages at top of form</li>
                            <li>Check date fields are valid dates</li>
                            <li>Verify amounts are numbers, not text</li>
                            <li>Check user permissions</li>
                        </ul>
                    </div>
                    
                    <h4>Issue: Features Not Working</h4>
                    <div class="step-box">
                        <strong>Solutions:</strong>
                        <ul>
                            <li>Hard refresh page: Ctrl+Shift+R (Cmd+Shift+R on Mac)</li>
                            <li>Clear browser cache</li>
                            <li>Try different browser</li>
                            <li>Check JavaScript console for errors (F12)</li>
                            <li>Contact system administrator</li>
                        </ul>
                    </div>
                    
                    <div class="tip-box">
                        <strong>💡 Still Need Help?</strong>
                        <ul>
                            <li>Use the 🤖 Assistant button - it can answer many questions</li>
                            <li>Check the FAQ section below</li>
                            <li>Review the getting started guide again</li>
                            <li>Contact your system administrator</li>
                        </ul>
                    </div>
                </div>
                
                <!-- ============ FAQ ============ -->
                <div class="manual-section" id="section-faq" style="display: none;">
                    <h2>❓ Frequently Asked Questions</h2>
                    
                    <h3>General Questions</h3>
                    
                    <div class="step-box">
                        <strong>Q: How often should I reconcile?</strong>
                        <p>
                            A: At minimum monthly, but weekly is recommended. Daily is ideal for high-volume accounts. 
                            More frequent reconciliation makes the process easier and helps catch errors quickly.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What if my bank statement and cashbook never match exactly?</strong>
                        <p>
                            A: They rarely match exactly! That's normal and expected. The reconciliation process 
                            identifies and documents the reconciling items (unpresented cheques, bank charges, etc.) 
                            that explain the difference.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I reconcile multiple bank accounts?</strong>
                        <p>
                            A: Yes! Create a separate Bank Reconciliation document for each bank account. Don't 
                            mix multiple accounts in one reconciliation.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What currency does the system support?</strong>
                        <p>
                            A: All currencies! The system uses your bank account's currency setting. Just ensure 
                            your statement amounts match the currency.
                        </p>
                    </div>
                    
                    <h3>Import Questions</h3>
                    
                    <div class="step-box">
                        <strong>Q: What format should my bank statement be in?</strong>
                        <p>
                            A: CSV or Excel (.xlsx, .xls). Most banks provide statements in these formats. 
                            Download from your online banking and import directly.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I import PDF bank statements?</strong>
                        <p>
                            A: Not directly. You'll need to convert PDF to CSV/Excel first using online tools 
                            or manually copy data to Excel.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What if my statement has multiple sheets in Excel?</strong>
                        <p>
                            A: The system reads the first sheet only. Either move your data to the first sheet 
                            or save that sheet separately as a new file.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I import the same file twice?</strong>
                        <p>
                            A: Yes, but enable "Skip Duplicates" option to prevent duplicate entries. The system 
                            will only import new transactions.
                        </p>
                    </div>
                    
                    <h3>Matching Questions</h3>
                    
                    <div class="step-box">
                        <strong>Q: How does intelligent matching work?</strong>
                        <p>
                            A: The system uses AI algorithms that consider amount similarity, date proximity, 
                            party name matching, and other factors to find probable matches with confidence scores.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What confidence level should I use?</strong>
                        <p>
                            A: Start with 60%. If you get too many false suggestions, increase to 70-80%. 
                            If getting too few matches, lower to 50%.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I undo a match?</strong>
                        <p>
                            A: Yes! Simply uncheck the "Rec" checkbox on the matched transactions. They'll 
                            become unmatched and available for matching again.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What's cross matching?</strong>
                        <p>
                            A: Cross matching allows debits in your books to match credits in the bank statement 
                            (and vice versa). Useful when transactions are recorded differently in your system vs bank.
                        </p>
                    </div>
                    
                    <h3>Reconciliation Questions</h3>
                    
                    <div class="step-box">
                        <strong>Q: What are unpresented cheques?</strong>
                        <p>
                            A: Cheques you've issued and recorded in your books, but recipients haven't cashed yet. 
                            They'll appear on future bank statements when cashed.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What are direct withdrawals?</strong>
                        <p>
                            A: Bank charges, fees, or automatic payments that appeared on your statement but 
                            you haven't recorded in your books yet. You need to create transactions for these.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Should I always aim for zero difference?</strong>
                        <p>
                            A: Yes, ideally. A small difference (< ₦1) due to rounding is acceptable. Larger 
                            differences indicate missing reconciling items or errors that need investigation.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I reconcile partial months?</strong>
                        <p>
                            A: Yes! Set your From Date and To Date to any period. Most people reconcile full 
                            calendar months, but you can do weekly or any custom period.
                        </p>
                    </div>
                    
                    <h3>Transaction Creation Questions</h3>
                    
                    <div class="step-box">
                        <strong>Q: Why are transactions created in Draft?</strong>
                        <p>
                            A: For your safety! You can review and edit transactions before submitting. This 
                            ensures accounts and cost centers are correct before posting to GL.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What if I don't want to create all transactions?</strong>
                        <p>
                            A: Remove unwanted entries from Direct Withdrawals/Lodgments tables before clicking 
                            Create Entries. Only entries in those tables will be created.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I edit created transactions?</strong>
                        <p>
                            A: Yes! While in Draft status, you can edit anything. After submission, you'll need 
                            to amend or cancel them following normal procedures.
                        </p>
                    </div>
                    
                    <h3>Technical Questions</h3>
                    
                    <div class="step-box">
                        <strong>Q: Does this work offline?</strong>
                        <p>
                            A: No, you need internet connection. This is a web-based system that requires server 
                            connection for all operations.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: What browsers are supported?</strong>
                        <p>
                            A: Chrome, Firefox, Safari, and Edge (latest versions). Chrome is recommended for 
                            best performance.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Is my data secure?</strong>
                        <p>
                            A: Yes! The system uses standard ERPNext security with role-based access control, 
                            audit trails, and encrypted connections.
                        </p>
                    </div>
                    
                    <div class="step-box">
                        <strong>Q: Can I access this on mobile?</strong>
                        <p>
                            A: The system works on mobile browsers but is optimized for desktop/laptop. For best 
                            experience, use a computer with a large screen.
                        </p>
                    </div>
                </div>
                
                <!-- ============ KEYBOARD SHORTCUTS ============ -->
                <div class="manual-section" id="section-shortcuts" style="display: none;">
                    <h2>⌨️ Keyboard Shortcuts</h2>
                    
                    <p>Speed up your work with these keyboard shortcuts:</p>
                    
                    <table class="manual-table">
                        <thead>
                            <tr>
                                <th>Action</th>
                                <th>Windows/Linux</th>
                                <th>Mac</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Open Intelligent Matching</td>
                                <td><span class="shortcut-key">Ctrl+M</span></td>
                                <td><span class="shortcut-key">Cmd+M</span></td>
                            </tr>
                            <tr>
                                <td>Open Import Dialog</td>
                                <td><span class="shortcut-key">Ctrl+I</span></td>
                                <td><span class="shortcut-key">Cmd+I</span></td>
                            </tr>
                            <tr>
                                <td>Print Statement</td>
                                <td><span class="shortcut-key">Ctrl+P</span></td>
                                <td><span class="shortcut-key">Cmd+P</span></td>
                            </tr>
                            <tr>
                                <td>Save Document</td>
                                <td><span class="shortcut-key">Ctrl+S</span></td>
                                <td><span class="shortcut-key">Cmd+S</span></td>
                            </tr>
                            <tr>
                                <td>Refresh Page</td>
                                <td><span class="shortcut-key">Ctrl+Shift+R</span></td>
                                <td><span class="shortcut-key">Cmd+Shift+R</span></td>
                            </tr>
                        </tbody>
                    </table>
                    
                    <h3>Grid Shortcuts</h3>
                    <p>When working in child tables (Bank Entries, Bank Statement, etc.):</p>
                    
                    <ul>
                        <li><span class="shortcut-key">Tab</span> - Move to next cell</li>
                        <li><span class="shortcut-key">Shift+Tab</span> - Move to previous cell</li>
                        <li><span class="shortcut-key">Enter</span> - Move to next row</li>
                        <li><span class="shortcut-key">Shift+Enter</span> - Add new row</li>
                        <li><span class="shortcut-key">Delete</span> - Clear cell content</li>
                    </ul>
                    
                    <h3>Tips for Power Users</h3>
                    
                    <div class="tip-box">
                        <strong>🚀 Speed Tips:</strong>
                        <ul>
                            <li>Learn the keyboard shortcuts - they're much faster than mouse clicks</li>
                            <li>Use quick filters to work with subsets of data</li>
                            <li>Keep manual matching dialog open while working</li>
                            <li>Use search boxes extensively - faster than scrolling</li>
                            <li>Master the bulk actions (Check All, Uncheck All, etc.)</li>
                        </ul>
                    </div>
                    
                    <div class="info-box">
                        <strong>📖 More Resources:</strong>
                        <ul>
                            <li>Explore the Actions menu - many features are there</li>
                            <li>Use the 🤖 Assistant for quick answers</li>
                            <li>Check 💡 Suggestions for anomaly detection</li>
                            <li>Review 📈 Progress regularly to track your work</li>
                            <li>Save this manual for future reference</li>
                        </ul>
                    </div>
                </div>
                
            </div>
        </div>
    `;
}