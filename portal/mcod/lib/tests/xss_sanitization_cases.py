"""Parametrized XSS sanitization cases used by ``test_utils``."""

import pytest

SCRIPT_TAG_XSS_CASES = [
    pytest.param(
        "<script/src=data:,alert()>",
        "",
        id="script-data-src",
    ),
    pytest.param(
        "<SCRIPT SRC=http://ha.ckers.org/xss.js></SCRIPT>",
        "",
        id="script-http-src",
    ),
    pytest.param(
        '<SCRIPT/XSS SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        "",
        id="script-xss-src",
    ),
    pytest.param(
        '<SCRIPT/SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        "",
        id="script-slash-src",
    ),
    pytest.param(
        "<SCRIPT SRC=http://ha.ckers.org/xss.js?< B >",
        "",
        id="malformed-script-src-with-tag",
    ),
    pytest.param(
        "<SCRIPT SRC=//ha.ckers.org/.j>",
        "",
        id="protocol-relative-script-src",
    ),
    pytest.param(
        "</script><script>alert('XSS');</script>",
        "alert('XSS');",
        id="script-after-closing-tag",
    ),
    pytest.param(
        '</TITLE><SCRIPT>alert("XSS");</SCRIPT>',
        'alert("XSS");',
        id="title-breakout-script",
    ),
    pytest.param(
        '<SCRIPT a=">" SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        "",
        id="script-attribute-greater-than",
    ),
    pytest.param(
        '<SCRIPT =">" SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        '" SRC="http://ha.ckers.org/xss.js"&gt;',
        id="script-bare-attribute-greater-than",
    ),
    pytest.param(
        '<SCRIPT a=">" \'\' SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        "",
        id="script-empty-attribute",
    ),
    pytest.param(
        '<SCRIPT "a=\'>\'" SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        "",
        id="script-quoted-attribute-name",
    ),
    pytest.param(
        '<SCRIPT a=`>` SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        '` SRC="http://ha.ckers.org/xss.js"&gt;',
        id="script-backtick-attribute",
    ),
    pytest.param(
        '<SCRIPT a=">\'>" SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        "",
        id="script-escaped-greater-than-attribute",
    ),
    pytest.param(
        '<SCRIPT>document.write("<SCRI");</SCRIPT>PT SRC="http://ha.ckers.org/xss.js"></SCRIPT>',
        'document.write("&lt;SCRI");PT SRC="http://ha.ckers.org/xss.js"&gt;',
        id="split-script-document-write",
    ),
    pytest.param(
        "<script>for((i)in(self))eval(i)(1)</script>",
        "for((i)in(self))eval(i)(1)",
        id="script-eval-content",
    ),
    pytest.param(
        "<scr<script>ipt>alert(1)</scr</script>ipt><scr<script>ipt>alert(1)</scr</script>ipt>",
        "ipt&gt;alert(1)ipt&gt;ipt&gt;alert(1)ipt&gt;",
        id="nested-script-obfuscation",
    ),
    pytest.param(
        "<sCR<script>iPt>alert(1)</SCr</script>IPt>",
        "iPt&gt;alert(1)IPt&gt;",
        id="mixed-case-nested-script",
    ),
]


EVENT_HANDLER_XSS_CASES = [
    pytest.param(
        "<marquee/onstart=alert()>",
        "",
        id="marquee-onstart",
    ),
    pytest.param(
        "<video/poster/onerror=alert()>",
        "",
        id="video-onerror",
    ),
    pytest.param(
        "<isindex/autofocus/onfocus=alert()>",
        "",
        id="isindex-onfocus",
    ),
    pytest.param(
        '<a onmouseover="alert(document.cookie)">xxs link</a>',
        '<a rel="noopener">xxs link</a>',
        id="anchor-onmouseover-quoted",
    ),
    pytest.param(
        "<a onmouseover=alert(document.cookie)>xxs link</a>",
        '<a rel="noopener">xxs link</a>',
        id="anchor-onmouseover-unquoted",
    ),
    pytest.param(
        "<IMG SRC=# onmouseover=\"alert('xxs')\">",
        '<img src="#">',
        id="img-fragment-src-onmouseover",
    ),
    pytest.param(
        "<IMG SRC= onmouseover=\"alert('xxs')\">",
        "<img src=\"onmouseover=&quot;alert('xxs')&quot;\">",
        id="img-empty-src-onmouseover-parser",
    ),
    pytest.param(
        "<IMG onmouseover=\"alert('xxs')\">",
        "<img>",
        id="img-onmouseover",
    ),
    pytest.param(
        '<IMG SRC=/ onerror="alert(String.fromCharCode(88,83,83))"></img>',
        '<img src="/">',
        id="img-relative-src-onerror",
    ),
    pytest.param(
        '<BODY onload!#$%&()*~+-_.,:;?@[/|\\]^`=alert("XSS")>',
        "",
        id="body-obfuscated-onload",
    ),
    pytest.param(
        "<BODY ONLOAD=alert('XSS')>",
        "",
        id="body-onload",
    ),
    pytest.param(
        "<BR SIZE=\"&{alert('XSS')}\">",
        "<br>",
        id="br-size-event-expression",
    ),
    pytest.param(
        '<IFRAME SRC=# onmouseover="alert(document.cookie)"></IFRAME>',
        "",
        id="iframe-onmouseover",
    ),
    pytest.param(
        "<w contenteditable id=x onfocus=alert()>",
        "",
        id="custom-tag-onfocus",
    ),
    pytest.param(
        "<svg/onload=%26%23097lert%26lpar;1337)>",
        "",
        id="svg-encoded-onload",
    ),
]


URL_AND_EMBEDDED_CONTENT_XSS_CASES = [
    pytest.param(
        "<IMG SRC=\"javascript:alert('XSS');\">",
        "<img>",
        id="img-javascript-src-quoted",
    ),
    pytest.param(
        "<IMG SRC=javascript:alert('XSS')>",
        "<img>",
        id="img-javascript-src-unquoted",
    ),
    pytest.param(
        "<IMG SRC=JaVaScRiPt:alert('XSS')>",
        "<img>",
        id="img-javascript-src-mixed-case",
    ),
    pytest.param(
        '<IMG SRC=javascript:alert("XSS")>',
        "<img>",
        id="img-javascript-src-double-quote",
    ),
    pytest.param(
        "<IMG SRC=`javascript:alert(\"RSnake says, 'XSS'\")`>",
        '<img src="`javascript:alert(&quot;RSnake">',
        id="img-javascript-src-backticks",
    ),
    pytest.param(
        "<IMG SRC=javascript:alert(String.fromCharCode(88,83,83))>",
        "<img>",
        id="img-javascript-src-charcode",
    ),
    pytest.param(
        '<INPUT TYPE="IMAGE" SRC="javascript:alert(\'XSS\');">',
        "",
        id="input-image-javascript-src",
    ),
    pytest.param(
        "<BODY BACKGROUND=\"javascript:alert('XSS')\">",
        "",
        id="body-javascript-background",
    ),
    pytest.param(
        "<IMG DYNSRC=\"javascript:alert('XSS')\">",
        "<img>",
        id="img-javascript-dynsrc",
    ),
    pytest.param(
        "<IMG LOWSRC=\"javascript:alert('XSS')\">",
        "<img>",
        id="img-javascript-lowsrc",
    ),
    pytest.param(
        "<IMG SRC='vbscript:msgbox(\"XSS\")'>",
        "<img>",
        id="img-vbscript-src",
    ),
    pytest.param(
        '<IMG SRC="livescript:[code]">',
        "<img>",
        id="img-livescript-src",
    ),
    pytest.param(
        "<BGSOUND SRC=\"javascript:alert('XSS');\">",
        "",
        id="bgsound-javascript-src",
    ),
    pytest.param(
        '<META HTTP-EQUIV="refresh" CONTENT="0;url=javascript:alert(\'XSS\');">',
        "",
        id="meta-refresh-javascript",
    ),
    pytest.param(
        '<META HTTP-EQUIV="refresh" CONTENT="0;url=data:text/html base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K">',
        "",
        id="meta-refresh-data",
    ),
    pytest.param(
        '<META HTTP-EQUIV="refresh" CONTENT="0; URL=http://;URL=javascript:alert(\'XSS\');">',
        "",
        id="meta-refresh-multiple-urls",
    ),
    pytest.param(
        "<IFRAME SRC=\"javascript:alert('XSS');\"></IFRAME>",
        "",
        id="iframe-javascript-src",
    ),
    pytest.param(
        "<FRAMESET><FRAME SRC=\"javascript:alert('XSS');\"></FRAMESET>",
        "",
        id="frame-javascript-src",
    ),
    pytest.param(
        "<TABLE BACKGROUND=\"javascript:alert('XSS')\">",
        "<table></table>",
        id="table-javascript-background",
    ),
    pytest.param(
        "<TABLE><TD BACKGROUND=\"javascript:alert('XSS')\">",
        "<table><tbody><tr><td></td></tr></tbody></table>",
        id="table-cell-javascript-background",
    ),
    pytest.param(
        "<BASE HREF=\"javascript:alert('XSS');//\">",
        "",
        id="base-javascript-href",
    ),
    pytest.param(
        '<OBJECT TYPE="text/x-scriptlet" DATA="http://ha.ckers.org/scriptlet.html"></OBJECT>',
        "",
        id="object-scriptlet-data",
    ),
    pytest.param(
        '<META HTTP-EQUIV="Set-Cookie" Content="USERID=<SCRIPT>alert(\'XSS\')</SCRIPT>">',
        "",
        id="meta-set-cookie-script",
    ),
    pytest.param(
        '<a href="data:text/html;base64,PHNjcmlwdD5hbGVydCgiSGVsbG8iKTs8L3NjcmlwdD4=">test</a>',
        '<a rel="noopener">test</a>',
        id="anchor-data-href",
    ),
]


ENCODED_AND_OBFUSCATED_XSS_CASES = [
    pytest.param(
        "<IMG SRC=&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;&#97;&#108;&#101;&#114;&#116;&#40;",
        "",
        id="img-decimal-entities-javascript",
    ),
    pytest.param(
        "&#39;&#88;&#83;&#83;&#39;&#41;>",
        "'XSS')&gt;",
        id="numeric-entities-plain-text",
    ),
    pytest.param(
        "<IMG SRC=&#0000106&#0000097&#0000118&#0000097&#0000115&#0000099&#0000114&#0000105&#0000112&#0000116&#0000058&#0000097&",  # noqa: E501
        "",
        id="img-zero-padded-decimal-entities",
    ),
    pytest.param(
        "#0000108&#0000101&#0000114&#0000116&#0000040&#0000039&#0000088&#0000083&#0000083&#0000039&#0000041>",
        "#0000108ert('XSS')&gt;",
        id="partial-numeric-entities-text",
    ),
    pytest.param(
        "<IMG SRC=&#x6A&#x61&#x76&#x61&#x73&#x63&#x72&#x69&#x70&#x74&#x3A&#x61&#x6C&#x65&#x72&#x74&#x28&#x27&#x58&#x53&#x53&#x27&#x29>",  # noqa: E501
        "<img>",
        id="img-hex-entities-javascript",
    ),
    pytest.param(
        "<IMG SRC=\"jav\tascript:alert('XSS');\">",
        "<img>",
        id="img-javascript-tab",
    ),
    pytest.param(
        "<IMG SRC=\"jav&#x09;ascript:alert('XSS');\">",
        "<img>",
        id="img-javascript-tab-entity",
    ),
    pytest.param(
        "<IMG SRC=\"jav&#x0A;ascript:alert('XSS');\">",
        "<img>",
        id="img-javascript-newline-entity",
    ),
    pytest.param(
        "<IMG SRC=\"jav&#x0D;ascript:alert('XSS');\">",
        "<img>",
        id="img-javascript-carriage-return-entity",
    ),
    pytest.param(
        "<IMG SRC=\" &#14;  javascript:alert('XSS');\">",
        "<img>",
        id="img-javascript-control-char",
    ),
    pytest.param(
        '<HEAD><META HTTP-EQUIV="CONTENT-TYPE" CONTENT="text/html; charset=UTF-7"> </HEAD>+ADw-SCRIPT+AD4-alert(\'XSS\');+ADw-/SCRIPT+AD4-',  # noqa: E501
        " +ADw-SCRIPT+AD4-alert('XSS');+ADw-/SCRIPT+AD4-",
        id="utf7-script-payload",
    ),
]


CSS_AND_STYLE_XSS_CASES = [
    pytest.param(
        "<STYLE>li {list-style-image: url(\"javascript:alert('XSS')\");}</STYLE><UL><LI>XSS</br>",
        "li {list-style-image: url(\"javascript:alert('XSS')\");}<ul><li>XSS<br></li></ul>",
        id="style-list-image-and-list",
    ),
    pytest.param(
        '<LINK REL="stylesheet" HREF="javascript:alert(\'XSS\');">',
        "",
        id="link-javascript-stylesheet",
    ),
    pytest.param(
        '<LINK REL="stylesheet" HREF="http://ha.ckers.org/xss.css">',
        "",
        id="external-stylesheet-link-tag",
    ),
    pytest.param(
        "<STYLE>@import'http://ha.ckers.org/xss.css';</STYLE>",
        "@import'http://ha.ckers.org/xss.css';",
        id="style-http-import",
    ),
    pytest.param(
        '<META HTTP-EQUIV="Link" Content="<http://ha.ckers.org/xss.css>; REL=stylesheet">',
        "",
        id="meta-link-header",
    ),
    pytest.param(
        '<STYLE>BODY{-moz-binding:url("http://ha.ckers.org/xssmoz.xml#xss")}</STYLE>',
        'BODY{-moz-binding:url("http://ha.ckers.org/xssmoz.xml#xss")}',
        id="style-moz-binding",
    ),
    pytest.param(
        "<STYLE>@im\\port'\\ja\\vasc\\ript:alert(\"XSS\")';</STYLE>",
        "@im\\port'\\ja\\vasc\\ript:alert(\"XSS\")';",
        id="style-obfuscated-javascript-import",
    ),
    pytest.param(
        "<IMG STYLE=\"xss:expr/*XSS*/ession(alert('XSS'))\">",
        '<img style="">',
        id="img-obfuscated-css-expression",
    ),
    pytest.param(
        'exp/*<A STYLE=\'no\\xss:noxss("*//*");',
        "exp/*",
        id="malformed-anchor-style",
    ),
    pytest.param(
        'xss:ex/*XSS*//*/*/pression(alert("XSS"))\'>',
        'xss:ex/*XSS*//*/*/pression(alert("XSS"))\'&gt;',
        id="css-expression-plain-text",
    ),
    pytest.param(
        "<STYLE TYPE=\"text/javascript\">alert('XSS');</STYLE>",
        "alert('XSS');",
        id="style-javascript-mime",
    ),
    pytest.param(
        "<STYLE>.XSS{background-image:url(\"javascript:alert('XSS')\");}</STYLE><A CLASS=XSS></A>",
        '.XSS{background-image:url("javascript:alert(\'XSS\')");}<a rel="noopener"></a>',
        id="style-javascript-background-and-anchor",
    ),
    pytest.param(
        '<STYLE type="text/css">BODY{background:url("javascript:alert(\'XSS\')")}</STYLE>',
        "BODY{background:url(\"javascript:alert('XSS')\")}",
        id="style-javascript-background",
    ),
    pytest.param(
        "<XSS STYLE=\"xss:expression(alert('XSS'))\">",
        "",
        id="unknown-tag-css-expression",
    ),
    pytest.param(
        '<XSS STYLE="behavior: url(xss.htc);">',
        "",
        id="unknown-tag-css-behavior",
    ),
    pytest.param(
        "<DIV STYLE=\"background-image: url(javascript:alert('XSS'))\">",
        '<div style=""></div>',
        id="div-javascript-background-image",
    ),
    pytest.param(
        "<DIV STYLE=\"background-image:\\0075\\0072\\006C\\0028'\\006a\\0061\\0076\\0061\\0073\\0063\\0072\\0069\\0070\\0074\\003a\\0061\\006c\\0065\\0072\\0074\\0028.1027\\0058.1053\\0053\\0027\\0029'\\0029\">",  # noqa: E501
        '<div style=""></div>',
        id="div-escaped-javascript-background-image",
    ),
    pytest.param(
        "<DIV STYLE=\"background-image: url(&#1;javascript:alert('XSS'))\">",
        '<div style=""></div>',
        id="div-control-char-javascript-background-image",
    ),
    pytest.param(
        "<DIV STYLE=\"width: expression(alert('XSS'));\">",
        '<div style="width:expression(alert()"></div>',
        id="div-css-expression-width",
    ),
]


MALFORMED_HTML_AND_SERIALIZATION_XSS_CASES = [
    pytest.param(
        "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//--></SCRIPT>\">'><SCRIPT>alert(String.fromCharCode(88,83,83))</SCRIPT>",  # noqa: E501
        "';alert(String.fromCharCode(88,83,83))//';alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//\";alert(String.fromCharCode(88,83,83))//--&gt;\"&gt;'&gt;alert(String.fromCharCode(88,83,83))",  # noqa: E501
        id="script-breakout-charcode",
    ),
    pytest.param(
        "'';!--\"<XSS>=&{()}",
        "'';!--\"=&amp;{()}",
        id="unknown-xss-tag-and-ampersand",
    ),
    pytest.param(
        '0\\"autofocus/onfocus=alert(1)--><video/poster/onerror=prompt(2)>"-confirm(3)-"',
        '0\\"autofocus/onfocus=alert(1)--&gt;"-confirm(3)-"',
        id="malformed-video-tag-breakout",
    ),
    pytest.param(
        '<IMG """><SCRIPT>alert("XSS")</SCRIPT>">',
        '<img>alert("XSS")"&gt;',
        id="malformed-img-nested-script",
    ),
    pytest.param(
        '<<SCRIPT>alert("XSS");//<</SCRIPT>',
        '&lt;alert("XSS");//&lt;',
        id="nested-opening-angle-script",
    ),
    pytest.param(
        "<IMG SRC=\"javascript:alert('XSS')\"",
        "",
        id="unclosed-img-javascript-src",
    ),
    pytest.param(
        "<iframe src=http://ha.ckers.org/scriptlet.html <",
        "",
        id="malformed-iframe-tag",
    ),
    pytest.param(
        "\\\";alert('XSS');//",
        "\\\";alert('XSS');//",
        id="escaped-quote-plain-text",
    ),
    pytest.param(
        "¼script¾alert(¢XSS¢)¼/script¾",
        "¼script¾alert(¢XSS¢)¼/script¾",
        id="non-ascii-script-lookalike",
    ),
    pytest.param(
        "<!--[if gte IE 4]><SCRIPT>alert('XSS');</SCRIPT><![endif]-->",
        "<!--[if gte IE 4]><SCRIPT>alert('XSS');</SCRIPT><![endif]-->",
        id="conditional-comment",
    ),
    pytest.param(
        "<!--#exec cmd=\"/bin/echo '<SCR'\"--><!--#exec cmd=\"/bin/echo 'IPT SRC=http://ha.ckers.org/xss.js></SCRIPT>'\"-->",  # noqa: E501
        "<!--#exec cmd=\"/bin/echo '<SCR'\"--><!--#exec cmd=\"/bin/echo 'IPT SRC=http://ha.ckers.org/xss.js></SCRIPT>'\"-->",  # noqa: E501
        id="server-side-include-comments",
    ),
    pytest.param(
        "<? echo('<SCR)';echo('IPT>alert(\"XSS\")</SCRIPT>'); ?>",
        "<!--? echo('<SCR)';echo('IPT-->alert(\"XSS\")'); ?&gt;",
        id="php-processing-instruction",
    ),
    pytest.param(
        '0\\"autofocus/onfocus=alert(1)--><video/poster/ error=prompt(2)>"-confirm(3)-"',
        '0\\"autofocus/onfocus=alert(1)--&gt;"-confirm(3)-"',
        id="malformed-video-error-attribute",
    ),
    pytest.param(
        "veris-->group<svg/onload=alert(/XSS/)//",
        "veris--&gt;group",
        id="malformed-svg-after-comment-close",
    ),
    pytest.param(
        "#\"><img src=M onerror=alert('XSS');>",
        '#"&gt;<img src="M">',
        id="prefixed-img-onerror",
    ),
    pytest.param(
        "element[attribute='<img src=x onerror=alert('XSS');>",
        'element[attribute=\'<img src="x">',
        id="embedded-img-in-text",
    ),
    pytest.param(
        '[<blockquote cite="]">[" onmouseover="alert(\'RVRSH3LL_XSS\');" ]',
        '[<blockquote>[" onmouseover="alert(\'RVRSH3LL_XSS\');" ]</blockquote>',
        id="malformed-blockquote-cite",
    ),
    pytest.param(
        "%22;alert%28%27RVRSH3LL_XSS%29//",
        "%22;alert%28%27RVRSH3LL_XSS%29//",
        id="percent-encoded-payload",
    ),
    pytest.param(
        "javascript:alert%281%29;",
        "javascript:alert%281%29;",
        id="percent-encoded-javascript-text",
    ),
    pytest.param(
        'alert;pg("XSS")',
        'alert;pg("XSS")',
        id="harmless-alert-like-text",
    ),
]


SAFE_HTTP_URL_CASES = [
    pytest.param(
        '<IMG SRC="http://www.thesiteyouareon.com/somecommand.php?somevariables=maliciouscode">',
        '<img src="http://www.thesiteyouareon.com/somecommand.php?somevariables=maliciouscode">',
        id="allowed-http-img-src",
    ),
    pytest.param(
        '<A HREF="http://66.102.7.147/">XSS</A>',
        '<a href="http://66.102.7.147/" rel="noopener">XSS</a>',
        id="allowed-http-anchor",
    ),
]


XSS_SANITIZATION_CASES = [
    *SCRIPT_TAG_XSS_CASES,
    *EVENT_HANDLER_XSS_CASES,
    *URL_AND_EMBEDDED_CONTENT_XSS_CASES,
    *ENCODED_AND_OBFUSCATED_XSS_CASES,
    *CSS_AND_STYLE_XSS_CASES,
    *MALFORMED_HTML_AND_SERIALIZATION_XSS_CASES,
    *SAFE_HTTP_URL_CASES,
]
