"""
Cookie 格式验证测试
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from core.cookie_storage import validate_netscape_cookie_format, clean_cookie_content


class TestCookieValidation:
    """Cookie 格式验证测试"""
    
    def test_valid_cookie_format(self):
        """测试有效的 Cookie 格式"""
        content = """# Netscape HTTP Cookie File
.douyin.com	TRUE	/	FALSE	1772086773	sessionid	abc123
.douyin.com	TRUE	/	TRUE	1772086773	secure_cookie	xyz789
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == True
        assert len(errors) == 0
        assert "sessionid" in cleaned
    
    def test_empty_name_field(self):
        """测试空的 name 字段"""
        content = """# Netscape HTTP Cookie File
www.douyin.com	FALSE	/	FALSE	1798438806		douyin.com
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 1
        assert "name 为空" in errors[0]
    
    def test_empty_domain_field(self):
        """测试空的 domain 字段"""
        content = """	TRUE	/	FALSE	1772086773	cookie_name	cookie_value
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 1
        assert "domain 为空" in errors[0]
    
    def test_invalid_flag_field(self):
        """测试无效的 flag 字段"""
        content = """.douyin.com	INVALID	/	FALSE	1772086773	cookie_name	cookie_value
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 1
        assert "flag 字段无效" in errors[0]
    
    def test_invalid_secure_field(self):
        """测试无效的 secure 字段"""
        content = """.douyin.com	TRUE	/	INVALID	1772086773	cookie_name	cookie_value
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 1
        assert "secure 字段无效" in errors[0]
    
    def test_invalid_expiration_field(self):
        """测试无效的 expiration 字段"""
        content = """.douyin.com	TRUE	/	FALSE	not_a_number	cookie_name	cookie_value
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 1
        assert "expiration 字段无效" in errors[0]
    
    def test_insufficient_fields(self):
        """测试字段数量不足"""
        content = """.douyin.com	TRUE	/	FALSE	1772086773
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 1
        assert "字段数量不足" in errors[0]
    
    def test_comments_and_empty_lines_preserved(self):
        """测试注释和空行被保留"""
        content = """# Netscape HTTP Cookie File
# This is a comment

.douyin.com	TRUE	/	FALSE	1772086773	sessionid	abc123

# Another comment
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == True
        assert "# Netscape HTTP Cookie File" in cleaned
        assert "# This is a comment" in cleaned
        assert "# Another comment" in cleaned
    
    def test_multiple_errors(self):
        """测试多个错误"""
        content = """# Netscape HTTP Cookie File
www.douyin.com	FALSE	/	FALSE	1798438806		douyin.com
	TRUE	/	FALSE	1772086773	cookie_name	cookie_value
.douyin.com	INVALID	/	FALSE	1772086773	cookie_name	cookie_value
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == False
        assert len(errors) == 3
    
    def test_clean_cookie_content(self):
        """测试清理 Cookie 内容"""
        content = """# Netscape HTTP Cookie File
.douyin.com	TRUE	/	FALSE	1772086773	valid_cookie	value1
www.douyin.com	FALSE	/	FALSE	1798438806		invalid_empty_name
.douyin.com	TRUE	/	TRUE	1772086773	another_valid	value2
"""
        cleaned = clean_cookie_content(content)
        
        # 有效的 Cookie 应该被保留
        assert "valid_cookie" in cleaned
        assert "another_valid" in cleaned
        # 无效的 Cookie 应该被移除
        assert "invalid_empty_name" not in cleaned
    
    def test_real_douyin_cookie_sample(self):
        """测试真实的抖音 Cookie 样本（部分）"""
        content = """.douyin.com	TRUE	/	FALSE	1767075597	feed_cache_data	%7B%22uuid%22%3A%2211323569%22%7D
.douyin.com	TRUE	/	FALSE	1772086785	bd_ticket_guard_client_data_v2	eyJyZWVfcHVibGljX2tleSI6IkJORzhhVGw5NEJETTJ
.douyin.com	TRUE	/	FALSE	1798438781	odin_tt	c4114197ff7390ac84a554716117c38db2d90792717e0c6ae5cb6001d2da6635
"""
        is_valid, errors, cleaned = validate_netscape_cookie_format(content)
        
        assert is_valid == True
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
