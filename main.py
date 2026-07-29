import discord
from discord.ext import commands
import aiohttp
import re
import json
import base64
import zlib
import io
import os

TOKEN = "MTUzMjExODQxNDkwMDk4NTkzMA.GxL3lg.cHEjjMQ7nsyu8XCjou5f40pXyU1ha2RHN2bX1c"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=".", intents=intents, help_command=None)

COMMANDS_LIST = """
`.l <link/loadstring>` - Detect protection → Deobfuscate → Send result as file
`.get <link/loadstring>` - Fetch raw full source code → Send as file
`.env <link/loadstring>` - Bypass anti-envlog → Run envlog scan → Send full report
`.cmds` - Show this command list
"""

def simple_xor_decode(data: str, key: str) -> str:
    result = []
    key_len = len(key)
    for i, char in enumerate(data):
        key_char = ord(key[i % key_len])
        result.append(chr(ord(char) ^ key_char))
    return ''.join(result)

async def fetch_content(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.1 Safari/537.36",
            "Referer": "https://roblox.com/"
        }
        async with session.get(url, headers=headers) as resp:
            return await resp.text()

def detect_and_deobf(code: str) -> str:
    original = code
    results = []
    
    if "Lunr" in code or "return(function" in code and "local L={" in code:
        results.append("[✓] Detected: Lunr Obfuscation")
        try:
            code = re.sub(r'-- This file was protected using Lunr.*?\n', '', code, flags=re.DOTALL)
            results.append("[+] Applied: Lunr unpack method")
        except: pass
    
    if "Luraph" in code or "bxor" in code and "string.gsub" in code:
        results.append("[✓] Detected: Luraph / Custom XOR")
        try:
            matches = re.findall(r'["\']([A-Za-z0-9+/=]{20,})["\']', code)
            for m in matches:
                try:
                    decoded = base64.b64decode(m).decode(errors="ignore")
                    if decoded and len(decoded) > 10:
                        code = code.replace(m, f"-- DECODED:\n{decoded}\n{m}")
                except: pass
        except: pass
    
    if "Prometheus" in code or "local _=getgenv" in code:
        results.append("[✓] Detected: Prometheus / Control Flow")
    
    if base64.b64encode(base64.b64decode(code, validate=False)) == code.encode():
        results.append("[✓] Detected: Raw Base64")
        try:
            code = base64.b64decode(code).decode(errors="replace")
        except: pass
    
    results.append("\n=== BEST EFFORT DEOBFUSCATED RESULT ===\n")
    return '\n'.join(results) + code

async def envlog_scan(code: str) -> str:
    report = ["=== ENVIRONMENT LOGGER ANALYSIS ==="]
    bypassed = code
    
    anti_patterns = [
        ("_ENVLOG", "Anti-Envlog Variable Check"),
        ("_GALACTIC", "Anti-Logger Check"),
        ("debug.getupvalue", "Debug Interception Check"),
        ("Kick.*tampered", "Kick on Tamper/Log"),
        ("loadstring.*~=", "Function Hook Detection"),
        ("while true do end", "Infinite Loop Freeze"),
        ("os.exit", "Force Close Script")
    ]
    
    found = []
    for pattern, desc in anti_patterns:
        if pattern in bypassed:
            found.append(f"[!] FOUND: {desc}")
            bypassed = bypassed.replace(pattern, f"-- BYPASSED: {pattern}")
    
    if found:
        report.append("\n".join(found))
        report.append("\n[+] Applied: Anti-envlog marker bypass")
    else:
        report.append("[✓] No strong anti-envlog measures found")
    
    report.append("\n=== SCANNED SOURCE ===")
    return '\n'.join(report) + '\n' + bypassed


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} | Ready to use")


@bot.command(name="cmds")
async def show_commands(ctx):
    emb = discord.Embed(title="🔧 RblXLua Tool Commands", color=0x2b2d31)
    emb.add_field(name="Commands", value=COMMANDS_LIST, inline=False)
    emb.set_footer(text="All results sent as files for full view")
    await ctx.send(embed=emb)


@bot.command(name="l")
async def deobf_command(ctx, *, link: str):
    await ctx.send("🔍 Processing link and detecting protection...")
    try:
        if "loadstring" in link:
            url_match = re.search(r'https?://[^\s"\']+', link)
            if not url_match:
                return await ctx.send("❌ Could not find valid URL in loadstring")
            url = url_match.group(0)
        else:
            url = link.strip()
        
        code = await fetch_content(url)
        result = detect_and_deobf(code)
        
        file = discord.File(io.StringIO(result), filename="deobfuscated_result.lua")
        await ctx.send(f"✅ Deobfuscation complete for: `{url}`", file=file)
    
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")


@bot.command(name="get")
async def fetch_command(ctx, *, link: str):
    await ctx.send("📥 Fetching raw source...")
    try:
        if "loadstring" in link:
            url_match = re.search(r'https?://[^\s"\']+', link)
            if not url_match:
                return await ctx.send("❌ Could not find valid URL")
            url = url_match.group(0)
        else:
            url = link.strip()
        
        code = await fetch_content(url)
        
        file = discord.File(io.StringIO(code), filename="raw_fetched_source.lua")
        await ctx.send(f"✅ Successfully fetched: `{url}`", file=file)
    
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")


@bot.command(name="env")
async def envlog_command(ctx, *, link: str):
    await ctx.send("🔎 Scanning and bypassing anti-log measures...")
    try:
        if "loadstring" in link:
            url_match = re.search(r'https?://[^\s"\']+', link)
            if not url_match:
                return await ctx.send("❌ Could not find valid URL")
            url = url_match.group(0)
        else:
            url = link.strip()
        
        code = await fetch_content(url)
        result = await envlog_scan(code)
        
        file = discord.File(io.StringIO(result), filename="envlog_analysis.lua")
        await ctx.send(f"✅ Envlog scan complete for: `{url}`", file=file)
    
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)[:100]}")


bot.run(TOKEN)
