"""Code execution security validation."""

import ast
import re
import logging
from typing import List, Set, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class SecurityLevel(Enum):
    """Security violation levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityViolation:
    """Represents a security violation in code."""
    
    level: SecurityLevel
    message: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    code_snippet: Optional[str] = None
    rule_id: Optional[str] = None


class CodeSecurityValidator:
    """Validates R code for security violations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize code security validator.
        
        Args:
            config: Security configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config or {}
        
        # Default blocked functions
        self.blocked_functions = set(self.config.get('blocked_functions', [
            'system', 'shell', 'system2', 'Sys.setenv', 'Sys.unsetenv',
            'file.remove', 'file.create', 'dir.create', 'unlink',
            'download.file', 'url', 'readLines', 'writeLines',
            'source', 'eval', 'parse', 'get', 'assign', 'rm',
            'quit', 'q', 'stop'
        ]))
        
        # Default allowed packages
        self.allowed_packages = set(self.config.get('allowed_packages', [
            'base', 'utils', 'stats', 'graphics', 'datasets', 'methods',
            'grDevices', 'tools', 'parallel', 'grid', 'splines', 'stats4',
            'tcltk', 'compiler', 'survival'
        ]))
        
        # Dangerous patterns
        self.dangerous_patterns = [
            (r'system\s*\(', SecurityLevel.CRITICAL, "System command execution"),
            (r'shell\s*\(', SecurityLevel.CRITICAL, "Shell command execution"),
            (r'eval\s*\(', SecurityLevel.HIGH, "Dynamic code evaluation"),
            (r'parse\s*\(', SecurityLevel.HIGH, "Code parsing"),
            (r'source\s*\(', SecurityLevel.HIGH, "External code sourcing"),
            (r'file\.remove\s*\(', SecurityLevel.MEDIUM, "File deletion"),
            (r'unlink\s*\(', SecurityLevel.MEDIUM, "File/directory deletion"),
            (r'download\.file\s*\(', SecurityLevel.MEDIUM, "File download"),
            (r'Sys\.setenv\s*\(', SecurityLevel.MEDIUM, "Environment variable modification"),
            (r'quit\s*\(|q\s*\(', SecurityLevel.HIGH, "Session termination"),
            (r'\.Call\s*\(', SecurityLevel.HIGH, "Native code call"),
            (r'\.C\s*\(', SecurityLevel.HIGH, "C code call"),
            (r'\.Fortran\s*\(', SecurityLevel.HIGH, "Fortran code call"),
            (r'\.External\s*\(', SecurityLevel.HIGH, "External code call"),
            (r'dyn\.load\s*\(', SecurityLevel.CRITICAL, "Dynamic library loading"),
            (r'library\.dynam\s*\(', SecurityLevel.HIGH, "Dynamic library loading"),
            (r'options\s*\(.*error\s*=', SecurityLevel.MEDIUM, "Error handling modification"),
            (r'sink\s*\(', SecurityLevel.LOW, "Output redirection"),
            (r'capture\.output\s*\(', SecurityLevel.LOW, "Output capture"),
        ]
        
        # File system patterns
        self.filesystem_patterns = [
            (r'file\.path\s*\(.*\.\./.*\)', SecurityLevel.HIGH, "Directory traversal attempt"),
            (r'["\']\.\./', SecurityLevel.HIGH, "Directory traversal in path"),
            (r'["\']~/', SecurityLevel.MEDIUM, "Home directory access"),
            (r'["\']/', SecurityLevel.MEDIUM, "Absolute path access"),
            (r'file\.exists\s*\(', SecurityLevel.LOW, "File existence check"),
            (r'list\.files\s*\(', SecurityLevel.LOW, "Directory listing"),
            (r'dir\s*\(', SecurityLevel.LOW, "Directory listing"),
        ]
        
        # Network patterns
        self.network_patterns = [
            (r'url\s*\(', SecurityLevel.MEDIUM, "URL connection"),
            (r'download\.file\s*\(', SecurityLevel.MEDIUM, "File download"),
            (r'readLines\s*\(.*http', SecurityLevel.MEDIUM, "HTTP request"),
            (r'curl\s*\(', SecurityLevel.MEDIUM, "HTTP request"),
            (r'httr::', SecurityLevel.MEDIUM, "HTTP library usage"),
            (r'RCurl::', SecurityLevel.MEDIUM, "HTTP library usage"),
        ]
        
        # Compile all patterns
        self.all_patterns = (
            self.dangerous_patterns + 
            self.filesystem_patterns + 
            self.network_patterns
        )
        
        # Compile regex patterns for performance
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), level, message)
            for pattern, level, message in self.all_patterns
        ]
    
    def validate_code(self, code: str) -> List[SecurityViolation]:
        """Validate R code for security violations.
        
        Args:
            code: R code to validate
            
        Returns:
            List of security violations found
        """
        violations = []
        
        try:
            # Split code into lines for line-by-line analysis
            lines = code.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                line_violations = self._check_line_security(line, line_num)
                violations.extend(line_violations)
            
            # Check for blocked functions
            function_violations = self._check_blocked_functions(code)
            violations.extend(function_violations)
            
            # Check for package usage
            package_violations = self._check_package_usage(code)
            violations.extend(package_violations)
            
            # Check for suspicious patterns
            pattern_violations = self._check_suspicious_patterns(code)
            violations.extend(pattern_violations)
            
        except Exception as e:
            self.logger.error(f"Error validating code security: {e}")
            violations.append(SecurityViolation(
                level=SecurityLevel.HIGH,
                message=f"Code validation error: {str(e)}",
                rule_id="VALIDATION_ERROR"
            ))
        
        return violations
    
    def _check_line_security(self, line: str, line_num: int) -> List[SecurityViolation]:
        """Check a single line for security violations.
        
        Args:
            line: Code line to check
            line_num: Line number
            
        Returns:
            List of violations found in the line
        """
        violations = []
        
        # Check against compiled patterns
        for pattern, level, message in self.compiled_patterns:
            matches = pattern.finditer(line)
            for match in matches:
                violations.append(SecurityViolation(
                    level=level,
                    message=message,
                    line_number=line_num,
                    column=match.start(),
                    code_snippet=line.strip(),
                    rule_id=f"PATTERN_{level.value.upper()}"
                ))
        
        return violations
    
    def _check_blocked_functions(self, code: str) -> List[SecurityViolation]:
        """Check for usage of blocked functions.
        
        Args:
            code: Code to check
            
        Returns:
            List of violations for blocked functions
        """
        violations = []
        
        for func_name in self.blocked_functions:
            # Create pattern to match function calls
            pattern = rf'\b{re.escape(func_name)}\s*\('
            matches = re.finditer(pattern, code, re.IGNORECASE)
            
            for match in matches:
                # Find line number
                line_num = code[:match.start()].count('\n') + 1
                
                violations.append(SecurityViolation(
                    level=SecurityLevel.HIGH,
                    message=f"Blocked function usage: {func_name}",
                    line_number=line_num,
                    column=match.start() - code.rfind('\n', 0, match.start()) - 1,
                    rule_id="BLOCKED_FUNCTION"
                ))
        
        return violations
    
    def _check_package_usage(self, code: str) -> List[SecurityViolation]:
        """Check for usage of non-allowed packages.
        
        Args:
            code: Code to check
            
        Returns:
            List of violations for package usage
        """
        violations = []
        
        # Check library() and require() calls
        library_pattern = r'(?:library|require)\s*\(\s*["\']?([^"\'\s\)]+)["\']?\s*\)'
        matches = re.finditer(library_pattern, code, re.IGNORECASE)
        
        for match in matches:
            package_name = match.group(1)
            if package_name not in self.allowed_packages:
                line_num = code[:match.start()].count('\n') + 1
                
                violations.append(SecurityViolation(
                    level=SecurityLevel.MEDIUM,
                    message=f"Non-allowed package usage: {package_name}",
                    line_number=line_num,
                    column=match.start() - code.rfind('\n', 0, match.start()) - 1,
                    rule_id="PACKAGE_NOT_ALLOWED"
                ))
        
        # Check :: namespace usage
        namespace_pattern = r'([a-zA-Z][a-zA-Z0-9\.]*)::'
        matches = re.finditer(namespace_pattern, code)
        
        for match in matches:
            package_name = match.group(1)
            if package_name not in self.allowed_packages:
                line_num = code[:match.start()].count('\n') + 1
                
                violations.append(SecurityViolation(
                    level=SecurityLevel.MEDIUM,
                    message=f"Non-allowed package namespace usage: {package_name}",
                    line_number=line_num,
                    column=match.start() - code.rfind('\n', 0, match.start()) - 1,
                    rule_id="NAMESPACE_NOT_ALLOWED"
                ))
        
        return violations
    
    def _check_suspicious_patterns(self, code: str) -> List[SecurityViolation]:
        """Check for suspicious code patterns.
        
        Args:
            code: Code to check
            
        Returns:
            List of violations for suspicious patterns
        """
        violations = []
        
        # Check for very long strings (potential obfuscation)
        long_string_pattern = r'["\'][^"\']{200,}["\']'
        matches = re.finditer(long_string_pattern, code)
        
        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            violations.append(SecurityViolation(
                level=SecurityLevel.LOW,
                message="Suspiciously long string (potential obfuscation)",
                line_number=line_num,
                rule_id="LONG_STRING"
            ))
        
        # Check for base64-like strings
        base64_pattern = r'["\'][A-Za-z0-9+/]{40,}={0,2}["\']'
        matches = re.finditer(base64_pattern, code)
        
        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            violations.append(SecurityViolation(
                level=SecurityLevel.MEDIUM,
                message="Potential base64 encoded content",
                line_number=line_num,
                rule_id="BASE64_CONTENT"
            ))
        
        # Check for excessive nesting (potential complexity attack)
        nesting_level = 0
        max_nesting = 0
        for char in code:
            if char in '({[':
                nesting_level += 1
                max_nesting = max(max_nesting, nesting_level)
            elif char in ')}]':
                nesting_level = max(0, nesting_level - 1)
        
        if max_nesting > 20:
            violations.append(SecurityViolation(
                level=SecurityLevel.MEDIUM,
                message=f"Excessive nesting level: {max_nesting}",
                rule_id="EXCESSIVE_NESTING"
            ))
        
        return violations
    
    def is_code_safe(self, code: str, max_violations: int = 0, 
                     max_level: SecurityLevel = SecurityLevel.MEDIUM) -> bool:
        """Check if code is safe to execute.
        
        Args:
            code: Code to check
            max_violations: Maximum number of violations allowed
            max_level: Maximum security level allowed
            
        Returns:
            True if code is safe, False otherwise
        """
        violations = self.validate_code(code)
        
        # Filter violations by level
        level_order = [SecurityLevel.LOW, SecurityLevel.MEDIUM, 
                      SecurityLevel.HIGH, SecurityLevel.CRITICAL]
        max_level_index = level_order.index(max_level)
        
        significant_violations = [
            v for v in violations 
            if level_order.index(v.level) > max_level_index
        ]
        
        return len(significant_violations) <= max_violations
    
    def get_security_report(self, code: str) -> Dict[str, Any]:
        """Generate a comprehensive security report for code.
        
        Args:
            code: Code to analyze
            
        Returns:
            Security report dictionary
        """
        violations = self.validate_code(code)
        
        # Group violations by level
        violations_by_level = {level: [] for level in SecurityLevel}
        for violation in violations:
            violations_by_level[violation.level].append(violation)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(violations)
        
        return {
            "total_violations": len(violations),
            "violations_by_level": {
                level.value: len(viols) 
                for level, viols in violations_by_level.items()
            },
            "risk_score": risk_score,
            "is_safe": risk_score < 50,  # Threshold for safety
            "violations": [
                {
                    "level": v.level.value,
                    "message": v.message,
                    "line_number": v.line_number,
                    "column": v.column,
                    "code_snippet": v.code_snippet,
                    "rule_id": v.rule_id
                }
                for v in violations
            ],
            "recommendations": self._generate_recommendations(violations)
        }
    
    def _calculate_risk_score(self, violations: List[SecurityViolation]) -> int:
        """Calculate risk score based on violations.
        
        Args:
            violations: List of security violations
            
        Returns:
            Risk score (0-100)
        """
        score = 0
        level_weights = {
            SecurityLevel.LOW: 5,
            SecurityLevel.MEDIUM: 15,
            SecurityLevel.HIGH: 35,
            SecurityLevel.CRITICAL: 50
        }
        
        for violation in violations:
            score += level_weights[violation.level]
        
        return min(score, 100)  # Cap at 100
    
    def _generate_recommendations(self, violations: List[SecurityViolation]) -> List[str]:
        """Generate security recommendations based on violations.
        
        Args:
            violations: List of security violations
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Group by rule ID
        rule_counts = {}
        for violation in violations:
            if violation.rule_id:
                rule_counts[violation.rule_id] = rule_counts.get(violation.rule_id, 0) + 1
        
        # Generate specific recommendations
        if rule_counts.get("BLOCKED_FUNCTION", 0) > 0:
            recommendations.append(
                "Remove or replace blocked functions with safer alternatives"
            )
        
        if rule_counts.get("PACKAGE_NOT_ALLOWED", 0) > 0:
            recommendations.append(
                "Only use approved packages or request package approval"
            )
        
        if rule_counts.get("PATTERN_CRITICAL", 0) > 0:
            recommendations.append(
                "Remove critical security violations before execution"
            )
        
        if rule_counts.get("LONG_STRING", 0) > 0:
            recommendations.append(
                "Review long strings for potential obfuscation"
            )
        
        if not recommendations:
            recommendations.append("Code appears to be secure")
        
        return recommendations
    
    def add_blocked_function(self, function_name: str) -> None:
        """Add a function to the blocked list.
        
        Args:
            function_name: Name of function to block
        """
        self.blocked_functions.add(function_name)
        self.logger.info(f"Added blocked function: {function_name}")
    
    def remove_blocked_function(self, function_name: str) -> None:
        """Remove a function from the blocked list.
        
        Args:
            function_name: Name of function to unblock
        """
        self.blocked_functions.discard(function_name)
        self.logger.info(f"Removed blocked function: {function_name}")
    
    def add_allowed_package(self, package_name: str) -> None:
        """Add a package to the allowed list.
        
        Args:
            package_name: Name of package to allow
        """
        self.allowed_packages.add(package_name)
        self.logger.info(f"Added allowed package: {package_name}")
    
    def remove_allowed_package(self, package_name: str) -> None:
        """Remove a package from the allowed list.
        
        Args:
            package_name: Name of package to disallow
        """
        self.allowed_packages.discard(package_name)
        self.logger.info(f"Removed allowed package: {package_name}")