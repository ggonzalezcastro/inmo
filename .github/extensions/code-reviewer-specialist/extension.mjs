// Extension: code-reviewer-specialist
// Specializes in security, performance, patterns, and best practices review
// Focuses on actionable, high-signal issues only (not style/formatting)

import { joinSession } from "@github/copilot-sdk/extension";

const session = await joinSession({
    tools: [
        {
            name: "review_security_issues",
            description: "Scan code for security vulnerabilities: injection attacks, auth bypasses, credential leaks, unsafe dependencies, etc.",
            parameters: {
                type: "object",
                properties: {
                    file_path: { type: "string", description: "Path to file being reviewed" },
                    code_snippet: { type: "string", description: "Code snippet to analyze (max 2000 chars)" },
                    language: { type: "string", enum: ["typescript", "javascript", "python", "go", "rust", "java"], description: "Programming language" },
                },
                required: ["file_path", "code_snippet", "language"],
            },
            skipPermission: true,
            handler: async (args) => {
                const issues = analyzeSecurityPatterns(args.code_snippet, args.language);
                return {
                    textResultForLlm: formatSecurityReport(issues, args.file_path),
                    resultType: issues.length > 0 ? "success" : "success",
                };
            },
        },
        {
            name: "review_performance",
            description: "Identify performance bottlenecks: inefficient algorithms, N+1 queries, memory leaks, unnecessary renders, etc.",
            parameters: {
                type: "object",
                properties: {
                    file_path: { type: "string", description: "Path to file being reviewed" },
                    code_snippet: { type: "string", description: "Code snippet to analyze" },
                    language: { type: "string", enum: ["typescript", "javascript", "python", "go", "rust", "java"], description: "Language" },
                    context: { type: "string", description: "Optional context (e.g., 'database query', 'React component render')" },
                },
                required: ["file_path", "code_snippet", "language"],
            },
            skipPermission: true,
            handler: async (args) => {
                const issues = analyzePerformancePatterns(args.code_snippet, args.language, args.context);
                return {
                    textResultForLlm: formatPerformanceReport(issues, args.file_path),
                    resultType: "success",
                };
            },
        },
        {
            name: "review_patterns_and_design",
            description: "Check for design pattern violations, maintainability issues, complexity, SOLID principle breaches, etc.",
            parameters: {
                type: "object",
                properties: {
                    file_path: { type: "string", description: "File path" },
                    code_snippet: { type: "string", description: "Code to review" },
                    language: { type: "string", enum: ["typescript", "javascript", "python", "go", "rust", "java"] },
                },
                required: ["file_path", "code_snippet", "language"],
            },
            skipPermission: true,
            handler: async (args) => {
                const issues = analyzeDesignPatterns(args.code_snippet, args.language);
                return {
                    textResultForLlm: formatDesignReport(issues, args.file_path),
                    resultType: "success",
                };
            },
        },
        {
            name: "review_test_coverage",
            description: "Evaluate test quality, coverage gaps, missing edge cases, mock issues, etc.",
            parameters: {
                type: "object",
                properties: {
                    file_path: { type: "string", description: "Test file path" },
                    test_code: { type: "string", description: "Test code to review" },
                    language: { type: "string", enum: ["typescript", "javascript", "python", "go", "rust"] },
                },
                required: ["file_path", "test_code", "language"],
            },
            skipPermission: true,
            handler: async (args) => {
                const issues = analyzeTestQuality(args.test_code, args.language);
                return {
                    textResultForLlm: formatTestReport(issues, args.file_path),
                    resultType: "success",
                };
            },
        },
    ],
});

// Analysis functions - pattern matchers for real issues only
function analyzeSecurityPatterns(code, language) {
    const issues = [];
    
    // Language-specific security checks
    if (language === "javascript" || language === "typescript") {
        // SQL injection patterns
        if (code.match(/sql\s*`.*\$\{.*\}`|exec\s*\(.*\$\{/i)) {
            issues.push({
                severity: "critical",
                type: "SQL Injection",
                message: "Template string used in SQL query without parameterized statements",
            });
        }
        // Unsafe eval/Function
        if (code.match(/\b(eval|Function|setTimeout|setInterval)\s*\(.*\$\{|eval\s*\(/i)) {
            issues.push({
                severity: "critical",
                type: "Code Injection",
                message: "eval() or Function constructor used with unsanitized input",
            });
        }
        // Hardcoded credentials
        if (code.match(/(?:password|secret|api_key|token)\s*=\s*["'][\w\-]+["']/i)) {
            issues.push({
                severity: "critical",
                type: "Hardcoded Credentials",
                message: "Credentials appear to be hardcoded in source",
            });
        }
        // CORS bypass
        if (code.match(/Access-Control-Allow-Origin.*\*|credentials:\s*true.*\*-origin/i)) {
            issues.push({
                severity: "high",
                type: "CORS Misconfiguration",
                message: "Overly permissive CORS configuration detected",
            });
        }
    }
    
    if (language === "python") {
        // Pickle with untrusted data
        if (code.match(/pickle\.load|pickle\.loads/)) {
            issues.push({
                severity: "critical",
                type: "Unsafe Deserialization",
                message: "pickle.load() used; vulnerable to arbitrary code execution",
            });
        }
        // SQL injection
        if (code.match(/f['"]\s*SELECT.*\{|\bformat\s*\(.*SELECT/i)) {
            issues.push({
                severity: "critical",
                type: "SQL Injection",
                message: "String formatting used in SQL query; use parameterized queries",
            });
        }
    }
    
    return issues;
}

function analyzePerformancePatterns(code, language, context) {
    const issues = [];
    
    // N+1 query pattern
    if (context && context.includes("query") && code.match(/for\s*\(|forEach|map|\.each/) && code.match(/query|fetch|db\./)) {
        issues.push({
            severity: "high",
            type: "N+1 Query",
            message: "Database query inside loop detected; consider batch loading",
        });
    }
    
    // Inefficient React rendering
    if (language === "typescript" || language === "javascript") {
        if (code.match(/useState.*\[\]|useState.*\{\}/) && code.match(/useEffect.*\[\](?!.*dependency)/)) {
            issues.push({
                severity: "medium",
                type: "Unnecessary Re-renders",
                message: "Object/array created in state or dependencies; causes re-renders",
            });
        }
    }
    
    // Recursive without base case
    if (code.match(/function.*\{[\s\S]*?\1\s*\(|const.*=.*=>.*\1\s*\(/)) {
        issues.push({
            severity: "high",
            type: "Potential Stack Overflow",
            message: "Recursive function without clear base case visible",
        });
    }
    
    return issues;
}

function analyzeDesignPatterns(code, language) {
    const issues = [];
    
    // Long functions (complexity)
    const lines = code.split("\n").length;
    if (lines > 50) {
        issues.push({
            severity: "medium",
            type: "High Complexity",
            message: `Function is ${lines} lines; consider breaking into smaller functions (max ~30 lines)`,
        });
    }
    
    // God objects / too many parameters
    if (code.match(/function\s+\w+\s*\([^)]{150,}/)) {
        issues.push({
            severity: "medium",
            type: "Too Many Parameters",
            message: "Function has many parameters; consider passing object or using dependency injection",
        });
    }
    
    // Mutation of function parameters
    if (code.match(/(?:param|arg)\d*\.\w+\s*=/)) {
        issues.push({
            severity: "medium",
            type: "Parameter Mutation",
            message: "Function parameter is being mutated; prefer returning new value",
        });
    }
    
    return issues;
}

function analyzeTestQuality(testCode, language) {
    const issues = [];
    
    // No assertions
    if (!testCode.match(/expect|assert|should\(|\.toBe|\.toEqual/) && testCode.match(/it\(|describe\(|test\(/)) {
        issues.push({
            severity: "high",
            type: "No Assertions",
            message: "Test has no assertions; test will always pass",
        });
    }
    
    // Too many assertions in one test
    const assertCount = (testCode.match(/expect|assert/g) || []).length;
    if (assertCount > 5) {
        issues.push({
            severity: "medium",
            type: "Test Too Broad",
            message: `Test has ${assertCount} assertions; should test one behavior per test`,
        });
    }
    
    return issues;
}

// Formatting helpers
function formatSecurityReport(issues, filePath) {
    if (issues.length === 0) return `✅ No security issues found in ${filePath}`;
    
    let report = `🔒 Security Review: ${filePath}\n\n`;
    issues.forEach((issue) => {
        report += `⚠️ [${issue.severity.toUpperCase()}] ${issue.type}\n`;
        report += `   ${issue.message}\n\n`;
    });
    return report;
}

function formatPerformanceReport(issues, filePath) {
    if (issues.length === 0) return `⚡ No performance issues found in ${filePath}`;
    
    let report = `⚡ Performance Review: ${filePath}\n\n`;
    issues.forEach((issue) => {
        report += `⚠️ [${issue.severity}] ${issue.type}\n`;
        report += `   ${issue.message}\n\n`;
    });
    return report;
}

function formatDesignReport(issues, filePath) {
    if (issues.length === 0) return `📐 No design issues found in ${filePath}`;
    
    let report = `📐 Design & Maintainability: ${filePath}\n\n`;
    issues.forEach((issue) => {
        report += `⚠️ [${issue.severity}] ${issue.type}\n`;
        report += `   ${issue.message}\n\n`;
    });
    return report;
}

function formatTestReport(issues, filePath) {
    if (issues.length === 0) return `✅ Test quality looks good: ${filePath}`;
    
    let report = `🧪 Test Quality Review: ${filePath}\n\n`;
    issues.forEach((issue) => {
        report += `⚠️ [${issue.severity}] ${issue.type}\n`;
        report += `   ${issue.message}\n\n`;
    });
    return report;
}
