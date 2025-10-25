import os
import time
import asyncio
from datetime import datetime, date, timedelta
import requests
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Cấu hình
CONFIG = {
    "TELEGRAM_BOT_TOKEN": "7721369545:AAFQ5jnc5qgrJvhLxbNrtYx-SwAgSGKXDHo",
    "MAIN_ADMIN_ID": "6748479692",
    "ADMIN_USERNAME": "hahahe6",
    "LIKE_FF_API_NORMAL": "https://phucios1403.x10.mx/likeff/likefree3.php?uid={}&key=phucesign1403500k",
    "LIKE_FF_API_VIP": "https://phucios1403.x10.mx/likeff/likefree3_vip.php?uid={}&key=phucesign1403500k",
    "FILES": {
        "ADMIN_IDS": "admin.txt",  # Đã xóa /storage/emulated/0/Download/
        "GROUP_IDS": "id_box.txt",
        "GROUP_CD_IDS": "id_box_cd.txt",
        "VIP_IDS": "idlike.txt",
        "USER_BUFF": "user_buff_today.txt"
    }
}

# Biến toàn cục
VIP_BUFF_IDS = []
BOT_ENABLED = True
last_midnight = None
last_cleanup_date = None

# Hàm gửi thông báo lỗi cho admin
async def notify_admin(app, message):
    try:
        if app:
            await app.bot.send_message(chat_id=CONFIG["MAIN_ADMIN_ID"], text=f"🚨 *LỖI BOT: {message}*", parse_mode="Markdown")
    except Exception as e:
        print(f"Error notifying admin: {e}")

# Hàm gửi tin nhắn
async def send_simple_msg(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None):
    try:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"Error sending message: {e}")
        await notify_admin(context.application, f"Lỗi gửi tin nhắn: {e}")
        return False

# Load VIP và xóa ID hết hạn
def load_vip_buff_ids():
    global VIP_BUFF_IDS
    try:
        vip_ids = {}
        if not os.path.exists(CONFIG["FILES"]["VIP_IDS"]):
            print(f"{CONFIG['FILES']['VIP_IDS']} does not exist")
            VIP_BUFF_IDS = []
            return []
        with open(CONFIG["FILES"]["VIP_IDS"], "r") as f:
            lines = f.readlines()
        valid_lines = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                continue
            uid = parts[0]
            expire = int(parts[1])
            if expire > int(time.time()):
                vip_ids[uid] = expire
                valid_lines.append(line)
        with open(CONFIG["FILES"]["VIP_IDS"], "w") as f:
            f.writelines(valid_lines)
        VIP_BUFF_IDS = list(vip_ids.keys())
        return VIP_BUFF_IDS
    except Exception as e:
        print(f"Error loading VIP IDs: {e}")
        VIP_BUFF_IDS = []
        return []

# Xóa file user_buff_today.txt khi ngày mới
def cleanup_if_new_day():
    global last_cleanup_date
    today = date.today()
    if last_cleanup_date != today:
        try:
            if os.path.exists(CONFIG["FILES"]["USER_BUFF"]):
                os.remove(CONFIG["FILES"]["USER_BUFF"])
                print(f"Cleaned up {CONFIG['FILES']['USER_BUFF']}")
            last_cleanup_date = today
        except Exception as e:
            print(f"Error cleaning up user_buff_today: {e}")

# Kiểm tra user đã buff hôm nay chưa
def has_user_buffed_today(user_id: str) -> bool:
    try:
        cleanup_if_new_day()
        if not os.path.exists(CONFIG["FILES"]["USER_BUFF"]): 
            return False
        with open(CONFIG["FILES"]["USER_BUFF"], "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and parts[0] == user_id and parts[1] == str(date.today()):
                    return True
        return False
    except Exception as e:
        print(f"Error checking user buff status: {e}")
        return False

def mark_user_buffed(user_id: str):
    try:
        today = str(date.today())
        with open(CONFIG["FILES"]["USER_BUFF"], "a") as f:
            f.write(f"{user_id} {today}\n")
    except Exception as e:
        print(f"Error marking user buffed: {e}")

# Load danh sách nhóm
def load_allowed_groups():
    try:
        allowed_groups = {}
        if not os.path.exists(CONFIG["FILES"]["GROUP_IDS"]):
            print(f"{CONFIG['FILES']['GROUP_IDS']} does not exist")
            return {}
        with open(CONFIG["FILES"]["GROUP_IDS"], "r") as f:
            for line in f:
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2 and parts[1].startswith("-"):
                    name, group_id = parts
                    allowed_groups[group_id] = name
        return allowed_groups
    except Exception as e:
        print(f"Error loading allowed groups: {e}")
        return {}

def load_allowed_cd_groups():
    try:
        allowed_cd = {}
        if not os.path.exists(CONFIG["FILES"]["GROUP_CD_IDS"]):
            print(f"{CONFIG['FILES']['GROUP_CD_IDS']} does not exist")
            return {}
        with open(CONFIG["FILES"]["GROUP_CD_IDS"], "r") as f:
            for line in f:
                parts = line.strip().split(maxsplit=2)
                if len(parts) == 3 and parts[1].startswith("-") and parts[2].isdigit():
                    name, group_id, cd_id = parts
                    if group_id not in allowed_cd:
                        allowed_cd[group_id] = {}
                    allowed_cd[group_id][cd_id] = name
        return allowed_cd
    except Exception as e:
        print(f"Error loading allowed CD groups: {e}")
        return {}

# Kiểm tra nhóm được phép
def is_group_allowed(chat_id: str) -> bool:
    if not chat_id.startswith("-"):
        return True
    allowed = load_allowed_groups()
    cd_allowed = load_allowed_cd_groups()
    if chat_id in allowed or chat_id in cd_allowed:
        return True
    return False

# Kiểm tra admin
def is_main_admin(user_id): 
    return str(user_id) == CONFIG["MAIN_ADMIN_ID"]

def is_admin(user_id): 
    try:
        if is_main_admin(user_id): 
            return True
        if not os.path.exists(CONFIG["FILES"]["ADMIN_IDS"]): 
            print(f"{CONFIG['FILES']['ADMIN_IDS']} does not exist in is_admin")
            return False
        with open(CONFIG["FILES"]["ADMIN_IDS"], "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and parts[1].isdigit() and str(parts[1]) == user_id:
                    return True
        return False
    except Exception as e:
        print(f"Error checking admin status: {e}")
        return False

# Kiểm tra quyền
async def check_permission(update: Update, context: ContextTypes.DEFAULT_TYPE, is_admin_required=False, is_main_admin_required=False):
    user_id = str(update.effective_user.id)
    if not is_admin_required and not is_main_admin_required:
        return True
    if is_main_admin_required and not is_main_admin(user_id): 
        await send_simple_msg(update, context, "*🚨 Bạn không có quyền admin chính!*")
        print(f"Permission denied for user {user_id}: Not main admin")
        return False
    if is_admin_required and not is_admin(user_id): 
        await send_simple_msg(update, context, "*🚨 Bạn không có quyền admin!*")
        print(f"Permission denied for user {user_id}: Not admin")
        return False
    return True

# Kiểm tra trạng thái bot
async def check_bot_enabled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not BOT_ENABLED and not is_admin(user_id):
        await send_simple_msg(update, context, "*🌟 Bot đang bảo trì! Vui lòng thử lại sau.*")
        print(f"Bot disabled for user {user_id}")
        return False
    return True

# Load/save VIP
def load_vip_ids():
    try:
        if not os.path.exists(CONFIG["FILES"]["VIP_IDS"]): 
            print(f"{CONFIG['FILES']['VIP_IDS']} does not exist in load_vip_ids")
            return {}
        vip_ids = {}
        with open(CONFIG["FILES"]["VIP_IDS"], "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    vip_ids[parts[0]] = {"expire": int(parts[1])}
        return vip_ids
    except Exception as e:
        print(f"Error loading VIP IDs: {e}")
        return {}

def save_vip_ids(vip_ids):
    try:
        with open(CONFIG["FILES"]["VIP_IDS"], "w") as f:
            content = "\n".join(f"{uid} {info['expire']}" for uid, info in vip_ids.items())
            f.write(content + "\n")
    except Exception as e:
        print(f"Error saving VIP IDs: {e}")

def save_admin_ids(admin_ids):
    try:
        with open(CONFIG["FILES"]["ADMIN_IDS"], "w") as f:
            for name, id_ in admin_ids.items():
                if name != "main_admin":
                    f.write(f"{name} {id_}\n")
    except Exception as e:
        print(f"Error saving admin IDs: {e}")

# Kiểm tra API
async def check_api_status():
    try:
        response = requests.get(CONFIG["LIKE_FF_API_NORMAL"].format("123456789"), timeout=10)
        return response.status_code == 200
    except Exception:
        return False

# API functions
async def api_request(url, uid):
    max_retries = 3
    start_time = time.time()
    for attempt in range(max_retries):
        try:
            response = requests.get(url.format(uid), timeout=30)
            response.raise_for_status()
            try:
                data = response.json()
                api_time = round(time.time() - start_time, 4)
                return data, api_time
            except ValueError:
                return None, None
        except requests.RequestException:
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
            continue
    return None, None

async def buff_like(uid, is_vip=False):
    url = CONFIG["LIKE_FF_API_VIP"] if is_vip else CONFIG["LIKE_FF_API_NORMAL"]
    data, api_time = await api_request(url, uid)
    if is_vip and not data:
        data, api_time = await api_request(CONFIG["LIKE_FF_API_NORMAL"], uid)
    return _parse_buff_result_full(data, api_time) if data else {"success": False, "message": "Lỗi kết nối API", "api_time": api_time or 0}

def _parse_buff_result_full(data, api_time):
    if data.get("status") == "success":
        message = data.get("message", "").lower()
        likes_given = data.get("LikesGivenByAPI", 0)
        likes_before = data.get("LikesbeforeCommand", 0)
        likes_after = data.get("LikesafterCommand", 0)
        player_name = data.get("PlayerNickname", None)
        if not player_name:
            player_name = "Không rõ"
        if "max like hôm nay" in message or likes_given == 0:
            return {
                "success": True,
                "likes_given": 0,
                "likes_before": likes_before,
                "likes_after": likes_after,
                "player_name": player_name,
                "message": "Đã buff like hôm nay rồi!",
                "api_time": api_time
            }
        return {
            "success": True,
            "likes_given": likes_given,
            "likes_before": likes_before,
            "likes_after": likes_after,
            "player_name": player_name,
            "message": message,
            "api_time": api_time
        }
    return {"success": False, "message": "Lỗi API", "api_time": api_time}

# Gửi báo cáo đến nhóm
async def send_to_all_allowed_groups(app, message: str):
    try:
        normal_groups = load_allowed_groups()
        cd_groups = load_allowed_cd_groups()
        
        tasks = []
        for group_id in normal_groups:
            tasks.append(app.bot.send_message(
                chat_id=group_id, 
                text=message,
                parse_mode="Markdown"
            ))
        
        for group_id, topics in cd_groups.items():
            for cd_id in topics:
                tasks.append(app.bot.send_message(
                    chat_id=group_id, 
                    message_thread_id=int(cd_id), 
                    text=f"*═══════✨ AUTO BUFF VIP - #{cd_id} ✨═══════*\n\n{message}",
                    parse_mode="Markdown"
                ))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error sending to groups: {e}")
        await notify_admin(app, "Lỗi gửi báo cáo đến nhóm")

# Auto buff
async def perform_auto_buff(app, buff_type="KHỞI ĐỘNG"):
    if not await check_api_status():
        await notify_admin(app, "API không hoạt động, auto buff bị bỏ qua")
        return
    
    cleanup_if_new_day()
    load_vip_buff_ids()
    all_buff_ids = VIP_BUFF_IDS[:50]
    
    if not all_buff_ids:
        await notify_admin(app, "Không tìm thấy ID VIP nào để buff")
        return
    
    results = []
    success_count = 0
    sem = asyncio.Semaphore(3)
    
    async def buff_with_limit(uid):
        async with sem:
            try:
                result = await buff_like(uid, True)
                return uid, result
            except Exception:
                return uid, {"success": False, "message": "Lỗi xử lý", "api_time": 0}
    
    tasks = [buff_with_limit(uid) for uid in all_buff_ids]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        await notify_admin(app, "Lỗi xử lý auto buff")
        return
    
    for uid, result in results:
        if isinstance(result, Exception):
            continue
        if result["success"]: 
            success_count += 1
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    buff_message = f"*═══✨ AUTO BUFF VIP FREE FIRE ✨═══*\n" \
                   f"*🚀 Loại: {buff_type} | Thành Công: {success_count}/{len(all_buff_ids)}*\n\n" \
                   f"*💎 DANH SÁCH BUFF VIP 💎*\n"
    
    for uid, result in results:
        if isinstance(result, Exception):
            buff_message += f"➤ ID: *{uid}*\n" \
                           f"❌ Trạng Thái: *Lỗi xử lý*\n" \
                           f"⚡ Tốc Độ: *0s*\n" \
                           f"───────────────\n"
            continue
        if result["success"] and result["likes_given"] > 0:
            player_name = result["player_name"]
            likes_given = result["likes_given"]
            likes_before = result["likes_before"]
            likes_after = result["likes_after"]
            api_time = result["api_time"]
            buff_message += f"➤ Tên: *{player_name}*\n" \
                           f"➤ ID: *{uid}*\n" \
                           f"💖 Like Đã Gửi: *{likes_given} likes*\n" \
                           f"📉 Like Trước: *{likes_before}*\n" \
                           f"📈 Like Sau: *{likes_after}*\n" \
                           f"⚡ Tốc Độ: *{api_time}s*\n" \
                           f"───────────────\n"
        else:
            status = "✅" if result["success"] else "❌"
            msg = result.get('message', 'Lỗi API')
            api_time = result.get('api_time', 0)
            buff_message += f"➤ ID: *{uid}*\n" \
                           f"{status} Trạng Thái: *{msg}*\n" \
                           f"⚡ Tốc Độ: *{api_time}s*\n" \
                           f"───────────────\n"
    
    buff_message += f"*═══════❖ THÔNG TIN DỊCH VỤ ❖═══════*\n" \
                   f"⏰ Thời Gian: *{current_time}*\n" \
                   f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                   f"*═══════✨🌟✨═══════*"
    
    try:
        await send_to_all_allowed_groups(app, buff_message)
        await notify_admin(app, f"{buff_type} AUTO BUFF HOÀN TẤT: {success_count}/{len(all_buff_ids)}")
    except Exception:
        await notify_admin(app, "Lỗi gửi báo cáo auto buff")

# Auto buff loop
async def auto_buff_loop(app):
    global last_midnight
    while True:
        try:
            now = datetime.now()
            today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            next_midnight = today_midnight + timedelta(days=1)
            
            if last_midnight != today_midnight:
                last_midnight = today_midnight
                await perform_auto_buff(app, "00:00")
            
            seconds_until_next_midnight = (next_midnight - now).total_seconds()
            if seconds_until_next_midnight < 0:
                seconds_until_next_midnight += 24 * 3600
            await asyncio.sleep(seconds_until_next_midnight)
        except Exception:
            await notify_admin(app, "Lỗi trong auto buff")
            await asyncio.sleep(60)

# Reload VIP định kỳ
async def reload_vip_periodically(app):
    while True:
        try:
            load_vip_buff_ids()
        except Exception:
            await notify_admin(app, "Lỗi reload danh sách VIP")
        await asyncio.sleep(600)

# Lệnh /on
async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if BOT_ENABLED:
        message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                  f"✅ Bot đã đang *BẬT*! Không cần bật lại.\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
    else:
        BOT_ENABLED = True
        message = f"*═══════✨ BẬT BOT THÀNH CÔNG ✨═══════*\n\n" \
                  f"🚀 Bot đã được *BẬT* và sẵn sàng hoạt động!\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await notify_admin(context.application, "Bot đã được bật")
    await send_simple_msg(update, context, message)

# Lệnh /off
async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_ENABLED
    if not await check_permission(update, context, is_main_admin_required=True): return
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not BOT_ENABLED:
        message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                  f"❌ Bot đã đang *TẮT*! Không cần tắt lại.\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
    else:
        BOT_ENABLED = False
        message = f"*═══════✨ TẮT BOT THÀNH CÔNG ✨═══════*\n\n" \
                  f"🛑 Bot đã được *TẮT*. Các lệnh sẽ không hoạt động (trừ admin).\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await notify_admin(context.application, "Bot đã được tắt")
    await send_simple_msg(update, context, message)

# Lệnh /admin
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_admin_required=True): return
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"*═══════✨ MENU DÀNH CHO ADMIN ✨═══════*\n\n" \
              f"*💫 Lệnh Admin *\n" \
              f"• `/likeffvip <uid> <day>` - Thêm ID VIP\n" \
              f"• `/likefflai` - Tăng like lại cho tất cả ID VIP\n" \
              f"• `/listvip` - Xem danh sách ID VIP\n" \
              f"• `/status` - Kiểm tra trạng thái bot\n\n" \
              f"*💫 Lệnh Admin Chính *\n" \
              f"• `/yes <tên> <group_id>` - Cho phép nhóm dùng bot\n" \
              f"• `/no <tên> <group_id>` - Xóa nhóm khỏi danh sách\n" \
              f"• `/yes1 <tên> <group_id> <cd>` - Cho phép nhóm với chủ đề\n" \
              f"• `/no1 <tên> <group_id> <cd>` - Xóa nhóm chủ đề\n" \
              f"• `/on` - Bật bot\n" \
              f"• `/off` - Tắt bot\n" \
              f"• `/addadmin <tên> <id>` - Thêm admin\n" \
              f"• `/deladmin <tên>` - Xóa admin\n" \
              f"• `/list_idad` - Xem danh sách admin\n" \
              f"• `/listgroups` - Xem danh sách nhóm\n" \
              f"• `/clearfiles` - Xóa các file cấu hình bot\n\n" \
              f"*💫 Lệnh Chung *\n" \
              f"• `/buy` - Xem bảng giá VIP\n" \
              f"• `/like <uid>` - Tăng like miễn phí\n" \
              f"• `/menuff` - Xem menu lệnh\n\n" \
              f"*═══════❖ THÔNG TIN ❖═══════*\n" \
              f"⏰ Thời Gian: *{current_time}*\n" \
              f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
              f"*═══════✨🌟✨═══════*"
    await send_simple_msg(update, context, message)

# Lệnh /status
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_admin_required=True): return
    status = "BẬT" if BOT_ENABLED else "TẮT"
    vip_count = len(VIP_BUFF_IDS)
    api_status = "Hoạt động" if await check_api_status() else "Không hoạt động"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"*═══════✨ TRẠNG THÁI BOT FREE FIRE ✨═══════*\n\n" \
              f"🔄 Trạng Thái: *{status}*\n" \
              f"💎 Số ID VIP: *{vip_count}*\n" \
              f"🌐 API: *{api_status}*\n" \
              f"⏰ Thời Gian: *{current_time}*\n" \
              f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
              f"*═══════✨🌟✨═══════*"
    await send_simple_msg(update, context, message)

# Lệnh /like
async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    chat_id = str(update.effective_chat.id)
    if not is_group_allowed(chat_id):
        await send_simple_msg(update, context, "*🌟 Nhóm chưa được cấp phép sử dụng bot!*")
        return
    user_id = str(update.effective_user.id)
    
    if not is_main_admin(user_id) and has_user_buffed_today(user_id):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"*═══════✨ THÔNG BÁO TĂNG LIKE ✨═══════*\n\n" \
                  f"❌ *Đã buff like hôm nay rồi!*\n" \
                  f"📌 Vui lòng thử lại sau 00:00 hoặc mua gói VIP tại /buy\n" \
                  f"⚡ Tốc Độ API: *0 giây*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
        return
    
    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /like <uid>*")
        return
    
    uid = args[0]
    msg = await update.message.reply_text(f"Đang buff like cho iD: *{uid}*", parse_mode="Markdown")
    
    start_time = time.time()
    result = await buff_like(uid, False)
    api_time = result.get("api_time", round(time.time() - start_time, 4))
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if result["success"]:
        likes_given = result["likes_given"]
        if likes_given > 0:
            player_name = result["player_name"]
            likes_before = result["likes_before"]
            likes_after = result["likes_after"]
            likes_added = likes_after - likes_before
            report = f"*═══✨ BÁO CÁO TĂNG LIKE FREE FIRE ✨═══*\n\n" \
                     f"*🎮 Thông Tin Người Chơi*\n" \
                     f"➤ Tên: *{player_name}*\n" \
                     f"➤ ID: *{uid}*\n\n" \
                     f"*🔥 Kết Quả Buff Like 🔥*\n" \
                     f"✅ Trạng Thái: *THÀNH CÔNG*\n" \
                     f"💖 Like Đã Gửi: *{likes_given} likes*\n" \
                     f"📉 Like Trước: *{likes_before}*\n" \
                     f"📈 Like Sau: *{likes_after}*\n" \
                     f"↗ Tăng Thêm: *{likes_added} likes*\n\n" \
                     f"*═══════❖ THÔNG TIN DỊCH VỤ ❖═══════*\n" \
                     f"⚡ Tốc Độ API: *{api_time} giây*\n" \
                     f"🪙 Loại: *Thường (Free)*\n" \
                     f"⏰ Thời Gian: *{current_time}*\n" \
                     f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                     f"*═══════✨🌟✨═══════*"
            if not is_main_admin(user_id):
                mark_user_buffed(user_id)
        else:
            report = f"*═══════✨ THÔNG BÁO TĂNG LIKE ✨═══════*\n\n" \
                     f"❌ *Đã buff like hôm nay rồi!*\n" \
                     f"📌 Vui lòng thử lại sau 00:00 hoặc mua gói VIP tại /buy\n" \
                     f"⚡ Tốc Độ API: *{api_time} giây*\n" \
                     f"⏰ Thời Gian: *{current_time}*\n" \
                     f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                     f"*═══════✨🌟✨═══════*"
    else:
        report = f"*═══════✨ BÁO CÁO LỖI ✨═══════*\n\n" \
                 f"➤ ID: *{uid}*\n" \
                 f"❌ Lỗi: *{result.get('message', 'Lỗi API')}*\n" \
                 f"⚡ Tốc Độ API: *{api_time} giây*\n" \
                 f"⏰ Thời Gian: *{current_time}*\n" \
                 f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                 f"*═══════✨🌟✨═══════*"
    
    await msg.edit_text(report, parse_mode="Markdown")

# Lệnh /buy
async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    chat_id = str(update.effective_chat.id)
    if not is_group_allowed(chat_id):
        await send_simple_msg(update, context, "*🌟 Nhóm chưa được cấp phép sử dụng bot!*")
        return
    message = f"*═══════✨ BẢNG GIÁ VIP LIKE FF ✨═══════*\n\n" \
              f"*📦 GÓI NGẮN HẠN*\n" \
              f"*═══════🌟═══════*\n" \
              f"📌 1 Ngày    — *10.000đ*\n" \
              f"📌 3 Ngày    — *30.000đ*\n" \
              f"📌 7 Ngày    — *50.000đ*\n" \
              f"📌 10 Ngày   — *90.000đ*\n" \
              f"📌 30 Ngày   — *170.000đ*\n\n" \
              f"*💖 CHI TIẾT GÓI LIKES*\n" \
              f"💎 50K / 7 ngày — *700 Likes*\n" \
              f"💎 60K / 14 ngày — *1400 Likes*\n" \
              f"💎 170K / 30 ngày — *3000 Likes*\n\n" \
              f"*⚡ HOẠT ĐỘNG ỔN ĐỊNH*\n" \
              f"💎 *Giá tốt – Uy tín – Chất lượng*\n" \
              f"🔒 *Bảo mật & an toàn tuyệt đối*\n\n" \
              f"*📌 Dịch vụ thuê BOT Like FF tự động*\n" \
              f"✔️ Phù hợp cho anh em bận rộn\n" \
              f"✔️ Auto 100 likes mỗi ngày ✅\n\n" \
              f"*👑 Liên hệ: @{CONFIG['ADMIN_USERNAME']}*\n" \
              f"*═══════✨🌟✨═══════*"
    keyboard = [
        [
            InlineKeyboardButton("Gói 1 Ngày (10K)", callback_data="buy_1day"),
            InlineKeyboardButton("Gói 3 Ngày (30K)", callback_data="buy_3day")
        ],
        [
            InlineKeyboardButton("Gói 7 Ngày (50K)", callback_data="buy_7day"),
            InlineKeyboardButton("Gói 10 Ngày (90K)", callback_data="buy_10day")
        ],
        [
            InlineKeyboardButton("Gói 30 Ngày (170K)", callback_data="buy_30day"),
            InlineKeyboardButton("Xem Gói Likes", callback_data="vip_likes")
        ],
        [
            InlineKeyboardButton("Liên hệ Admin", url=f"https://t.me/{CONFIG['ADMIN_USERNAME']}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_simple_msg(update, context, message, reply_markup)

# Lệnh /menuff
async def menuff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    chat_id = str(update.effective_chat.id)
    if not is_group_allowed(chat_id):
        await send_simple_msg(update, context, "*🌟 Nhóm chưa được cấp phép sử dụng bot!*")
        return
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"*═══════✨ MENU FREE FIRE ✨═══════*\n\n" \
              f"*💫 Lệnh Dành Cho Người Dùng*\n" \
              f"• `/like <uid>` - Tăng like miễn phí (1 lần/ngày)\n" \
              f"• `/buy` - Xem bảng giá VIP\n" \
              f"📌 Ví dụ: `/like 7786937940`\n\n" \
              f"*═══════❖ THÔNG TIN ❖═══════*\n" \
              f"⏰ Thời Gian: *{current_time}*\n" \
              f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
              f"*═══════✨🌟✨═══════*"
    await send_simple_msg(update, context, message)

# Lệnh /likeffvip
async def likeffvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_admin_required=True): return
    args = context.args
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit(): 
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /likeffvip <uid> <day>*")
        return
    uid, days = args[0], int(args[1])
    vip_ids = load_vip_ids()
    expire_time = int(time.time()) + days * 86400
    vip_ids[uid] = {"expire": expire_time}
    save_vip_ids(vip_ids)
    expire_date = datetime.fromtimestamp(expire_time).strftime("%Y-%m-%d %H:%M:%S")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = f"*═══════✨ THÊM VIP THÀNH CÔNG ✨═══════*\n\n" \
              f"➤ ID: *{uid}*\n" \
              f"➤ Hết Hạn: *{expire_date}*\n" \
              f"⏰ Thời Gian: *{current_time}*\n" \
              f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
              f"*═══════✨🌟✨═══════*"
    await send_simple_msg(update, context, message)

# Lệnh /likefflai
async def likefflai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_admin_required=True): return
    load_vip_buff_ids()
    if not VIP_BUFF_IDS:
        await send_simple_msg(update, context, "*❌ Không tìm thấy ID VIP nào!*")
        return
    await perform_auto_buff(context.application, "THỦ CÔNG")

# Lệnh /listvip
async def listvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_admin_required=True): return
    vip_ids = load_vip_ids()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not vip_ids:
        await send_simple_msg(update, context, "*❌ Không có ID VIP nào!*")
        return
    text = f"*═══════✨ DANH SÁCH ID VIP ✨═══════*\n\n" \
           f"💎 Tổng Số: *{len(vip_ids)} ID*\n"
    for uid, info in vip_ids.items():
        expire_date = datetime.fromtimestamp(info["expire"]).strftime("%Y-%m-%d %H:%M")
        status = "✅" if info["expire"] > int(time.time()) else "❌"
        text += f"➤ ID: *{uid}*\n" \
                f"➤ Hết Hạn: *{expire_date}*\n" \
                f"➤ Trạng Thái: *{status}*\n" \
                f"───────────────\n"
    text += f"*═══════❖ THÔNG TIN ❖═══════*\n" \
            f"⏰ Thời Gian: *{current_time}*\n" \
            f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
            f"*═══════✨🌟✨═══════*"
    await send_simple_msg(update, context, text)

# Lệnh /yes
async def yes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    args = context.args
    if len(args) != 2 or not args[1].startswith("-"):
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /yes <tên> <group_id>*")
        return
    name, group_id = args
    allowed_groups = load_allowed_groups()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if group_id in allowed_groups:
        message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                  f"❌ Nhóm *{group_id}* đã được cấp phép với tên: *{allowed_groups[group_id]}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
        return
    for existing_name in allowed_groups.values():
        if existing_name == name:
            message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                      f"❌ Tên *{name}* đã được sử dụng cho nhóm khác!\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
            return
    try:
        with open(CONFIG["FILES"]["GROUP_IDS"], "a") as f:
            f.write(f"{name} {group_id}\n")
        message = f"*═══════✨ CẤP PHÉP NHÓM THÀNH CÔNG ✨═══════*\n\n" \
                  f"➤ Tên: *{name}*\n" \
                  f"➤ ID: *{group_id}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
    except Exception as e:
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi thêm nhóm *{name}* (*{group_id}*): *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /no
async def no_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    args = context.args
    if len(args) != 2:
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /no <tên> <group_id>*")
        return
    name, group_id = args
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if os.path.exists(CONFIG["FILES"]["GROUP_IDS"]):
            with open(CONFIG["FILES"]["GROUP_IDS"], "r") as f:
                lines = f.readlines()
            with open(CONFIG["FILES"]["GROUP_IDS"], "w") as f:
                for line in lines:
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2 and (parts[0] != name and parts[1] != group_id):
                        f.write(line)
            message = f"*═══════✨ XÓA NHÓM THÀNH CÔNG ✨═══════*\n\n" \
                      f"➤ Tên: *{name}*\n" \
                      f"➤ ID: *{group_id}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
        else:
            message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                      f"❌ Không tìm thấy nhóm:\n" \
                      f"➤ Tên: *{name}*\n" \
                      f"➤ ID: *{group_id}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
    except Exception as e:
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi xóa nhóm *{name}* (*{group_id}*): *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /yes1
async def yes1_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    args = context.args
    if len(args) != 3 or not args[1].startswith("-") or not args[2].isdigit():
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /yes1 <tên> <group_id> <cd>*")
        return
    name, group_id, cd_id = args
    allowed_cd = load_allowed_cd_groups()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if group_id in allowed_cd and cd_id in allowed_cd[group_id]:
        message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                  f"❌ Nhóm chủ đề *{group_id}* (*{cd_id}*) đã được cấp phép với tên: *{allowed_cd[group_id][cd_id]}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
        return
    for gid, topics in allowed_cd.items():
        for cid, n in topics.items():
            if n == name:
                message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                          f"❌ Tên *{name}* đã được sử dụng cho nhóm *{gid}* (chủ đề *{cid}*)!\n" \
                          f"⏰ Thời Gian: *{current_time}*\n" \
                          f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                          f"*═══════✨🌟✨═══════*"
                await send_simple_msg(update, context, message)
                return
    try:
        with open(CONFIG["FILES"]["GROUP_CD_IDS"], "a") as f:
            f.write(f"{name} {group_id} {cd_id}\n")
        message = f"*═══════✨ CẤP PHÉP NHÓM CHỦ ĐỀ THÀNH CÔNG ✨═══════*\n\n" \
                  f"➤ Tên: *{name}*\n" \
                  f"➤ ID: *{group_id}*\n" \
                  f"➤ Chủ Đề: *{cd_id}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
    except Exception as e:
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi thêm chủ đề *{name}* (*{group_id}* *{cd_id}*): *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /no1
async def no1_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    args = context.args
    if len(args) != 3:
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /no1 <tên> <group_id> <cd>*")
        return
    name, group_id, cd_id = args
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if os.path.exists(CONFIG["FILES"]["GROUP_CD_IDS"]):
            with open(CONFIG["FILES"]["GROUP_CD_IDS"], "r") as f:
                lines = f.readlines()
            with open(CONFIG["FILES"]["GROUP_CD_IDS"], "w") as f:
                for line in lines:
                    parts = line.strip().split(maxsplit=2)
                    if len(parts) == 3 and (parts[0] != name and parts[1] != group_id or parts[2] != cd_id):
                        f.write(line)
            message = f"*═══════✨ XÓA NHÓM CHỦ ĐỀ THÀNH CÔNG ✨═══════*\n\n" \
                      f"➤ Tên: *{name}*\n" \
                      f"➤ ID: *{group_id}*\n" \
                      f"➤ Chủ Đề: *{cd_id}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
        else:
            message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                      f"❌ Không tìm thấy nhóm chủ đề:\n" \
                      f"➤ Tên: *{name}*\n" \
                      f"➤ ID: *{group_id}*\n" \
                      f"➤ Chủ Đề: *{cd_id}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
    except Exception as e:
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi xóa chủ đề *{name}* (*{group_id}* *{cd_id}*): *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /listgroups
async def listgroups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    normal_groups = load_allowed_groups()
    cd_groups = load_allowed_cd_groups()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"*═══════✨ DANH SÁCH NHÓM ĐƯỢC PHÉP ✨═══════*\n\n" \
           f"*💎 Nhóm Thường ({len(normal_groups)})*\n"
    for group_id, name in sorted(normal_groups.items()):
        text += f"➤ Tên: *{name}*\n" \
                f"➤ ID: *{group_id}*\n" \
                f"───────────────\n"
    text += f"*💎 Nhóm Chủ Đề ({sum(len(topics) for topics in cd_groups.values())})*\n"
    for group_id in sorted(cd_groups.keys()):
        for cd_id, name in sorted(cd_groups[group_id].items()):
            text += f"➤ Tên: *{name}*\n" \
                    f"➤ ID: *{group_id}*\n" \
                    f"➤ Chủ Đề: *{cd_id}*\n" \
                    f"───────────────\n"
    text += f"*═══════❖ THÔNG TIN ❖═══════*\n" \
            f"⏰ Thời Gian: *{current_time}*\n" \
            f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
            f"*═══════✨🌟✨═══════*"
    await send_simple_msg(update, context, text)

# Lệnh /list_idad
async def list_idad_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): 
        print("Bot disabled or not enabled for /list_idad")
        return
    if not await check_permission(update, context, is_main_admin_required=True): 
        print("Permission denied for /list_idad")
        return
    admin_ids = {"main_admin": int(CONFIG["MAIN_ADMIN_ID"])}
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_path = CONFIG["FILES"]["ADMIN_IDS"]
    
    # Kiểm tra quyền truy cập file
    if os.path.exists(file_path):
        if not os.access(file_path, os.R_OK):
            print(f"Cannot read {file_path}: Permission denied")
            message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                      f"❌ Không thể đọc file admin.txt: *Quyền truy cập bị từ chối*\n" \
                      f"📌 Vui lòng kiểm tra quyền file: chmod 666 {file_path}\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
            return
        try:
            with open(file_path, "r") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 2 and parts[1].isdigit():
                        admin_ids[parts[0]] = int(parts[1])
        except Exception as e:
            print(f"Error reading {file_path} in list_idad_command: {e}")
            message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                      f"❌ Lỗi đọc file admin.txt: *{str(e)}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
            return
    else:
        print(f"{file_path} does not exist in list_idad_command")
    
    text = f"*═══════✨ DANH SÁCH ADMIN ✨═══════*\n\n" \
           f"💎 Tổng Số: *{len(admin_ids)} Admin*\n"
    for name, id_ in admin_ids.items():
        text += f"➤ Tên: *{name}*\n" \
                f"➤ ID: *{id_}*\n" \
                f"───────────────\n"
    text += f"*═══════❖ THÔNG TIN ❖═══════*\n" \
            f"⏰ Thời Gian: *{current_time}*\n" \
            f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
            f"*═══════✨🌟✨═══════*"
    
    try:
        await send_simple_msg(update, context, text)
    except Exception as e:
        print(f"Error sending list_idad response: {e}")
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi gửi danh sách admin: *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /addadmin
async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    args = context.args
    if len(args) != 2 or not args[1].isdigit():
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /addadmin <tên> <id>*")
        return
    name, user_id = args[0], int(args[1])
    admin_ids = {"main_admin": int(CONFIG["MAIN_ADMIN_ID"])}
    file_path = CONFIG["FILES"]["ADMIN_IDS"]
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and parts[1].isdigit():
                    admin_ids[parts[0]] = int(parts[1])
    
    admin_ids[name] = user_id
    try:
        if not os.access(os.path.dirname(file_path) or ".", os.W_OK):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                      f"❌ Không thể ghi file admin.txt: *Quyền truy cập bị từ chối*\n" \
                      f"📌 Vui lòng kiểm tra quyền thư mục: chmod 777 {os.path.dirname(file_path) or '.'}\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
            return
        save_admin_ids(admin_ids)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"*═══════✨ THÊM ADMIN THÀNH CÔNG ✨═══════*\n\n" \
                  f"➤ Tên: *{name}*\n" \
                  f"➤ ID: *{user_id}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
    except Exception as e:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi thêm admin *{name}* (*{user_id}*): *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /deladmin
async def deladmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): return
    if not await check_permission(update, context, is_main_admin_required=True): return
    args = context.args
    if len(args) != 1:
        await send_simple_msg(update, context, "*❌ Sai cú pháp: /deladmin <tên>*")
        return
    name = args[0]
    admin_ids = {"main_admin": int(CONFIG["MAIN_ADMIN_ID"])}
    file_path = CONFIG["FILES"]["ADMIN_IDS"]
    
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2 and parts[1].isdigit():
                    admin_ids[parts[0]] = int(parts[1])
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if name in admin_ids and name != "main_admin":
        del admin_ids[name]
        try:
            if not os.access(os.path.dirname(file_path) or ".", os.W_OK):
                message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                          f"❌ Không thể ghi file admin.txt: *Quyền truy cập bị từ chối*\n" \
                          f"📌 Vui lòng kiểm tra quyền thư mục: chmod 777 {os.path.dirname(file_path) or '.'}\n" \
                          f"⏰ Thời Gian: *{current_time}*\n" \
                          f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                          f"*═══════✨🌟✨═══════*"
                await send_simple_msg(update, context, message)
                return
            save_admin_ids(admin_ids)
            message = f"*═══════✨ XÓA ADMIN THÀNH CÔNG ✨═══════*\n\n" \
                      f"➤ Tên: *{name}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
        except Exception as e:
            message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                      f"❌ Lỗi xóa admin *{name}*: *{str(e)}*\n" \
                      f"⏰ Thời Gian: *{current_time}*\n" \
                      f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                      f"*═══════✨🌟✨═══════*"
            await send_simple_msg(update, context, message)
    else:
        message = f"*═══════✨ THÔNG BÁO ✨═══════*\n\n" \
                  f"❌ Không tìm thấy admin:\n" \
                  f"➤ Tên: *{name}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Lệnh /clearfiles
async def clearfiles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_bot_enabled(update, context): 
        print("Bot disabled or not enabled for /clearfiles")
        return
    if not await check_permission(update, context, is_main_admin_required=True): 
        print("Permission denied for /clearfiles")
        return
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    deleted_files = []
    failed_files = []
    max_retries = 3
    
    # Danh sách file cần xóa
    files_to_delete = [
        CONFIG["FILES"]["ADMIN_IDS"],
        CONFIG["FILES"]["GROUP_IDS"],
        CONFIG["FILES"]["GROUP_CD_IDS"],
        CONFIG["FILES"]["VIP_IDS"],
        CONFIG["FILES"]["USER_BUFF"]
    ]
    
    # Kiểm tra quyền thư mục
    dir_path = os.path.dirname(files_to_delete[0]) or "."
    if not os.access(dir_path, os.W_OK):
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Không thể ghi vào thư mục: *{dir_path}*\n" \
                  f"📌 Vui lòng cấp quyền: chmod 777 {dir_path}\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)
        print(f"Cannot write to {dir_path}: Permission denied")
        return
    
    # Thử xóa từng file
    for file_path in files_to_delete:
        for attempt in range(max_retries):
            try:
                if not os.path.exists(file_path):
                    print(f"File does not exist: {file_path}")
                    break
                if not os.access(file_path, os.W_OK):
                    print(f"Cannot write to {file_path}: Permission denied")
                    failed_files.append((os.path.basename(file_path), "Quyền truy cập bị từ chối"))
                    break
                os.remove(file_path)
                deleted_files.append(os.path.basename(file_path))
                print(f"Deleted file: {file_path}")
                break
            except Exception as e:
                print(f"Error deleting {file_path} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    failed_files.append((os.path.basename(file_path), str(e)))
                time.sleep(1)  # Chờ trước khi thử lại
    
    # Xóa danh sách VIP trong bộ nhớ
    global VIP_BUFF_IDS
    VIP_BUFF_IDS = []
    
    # Tạo thông báo
    message = f"*═══════✨ XÓA FILE CẤU HÌNH ✨═══════*\n\n"
    if deleted_files:
        message += f"✅ Đã xóa các file:\n"
        for file in deleted_files:
            message += f"➤ *{file}*\n"
    else:
        message += f"⚠️ Không có file nào được xóa.\n"
    
    if failed_files:
        message += f"\n❌ Lỗi khi xóa:\n"
        for file, error in failed_files:
            message += f"➤ *{file}*: {error}\n"
    
    message += f"\n*═══════❖ THÔNG TIN ❖═══════*\n" \
              f"⏰ Thời Gian: *{current_time}*\n" \
              f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
              f"*═══════✨🌟✨═══════*"
    
    try:
        await send_simple_msg(update, context, message)
    except Exception as e:
        print(f"Error sending clearfiles response: {e}")
        message = f"*═══════✨ LỖI ✨═══════*\n\n" \
                  f"❌ Lỗi gửi thông báo xóa file: *{str(e)}*\n" \
                  f"⏰ Thời Gian: *{current_time}*\n" \
                  f"👑 Chủ Sở Hữu: *@{CONFIG['ADMIN_USERNAME']}*\n" \
                  f"*═══════✨🌟✨═══════*"
        await send_simple_msg(update, context, message)

# Button callback
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    packages = {
        "buy_1day": f"Gói 1 Ngày - *10.000đ*\nLiên hệ: *@{CONFIG['ADMIN_USERNAME']}*",
        "buy_3day": f"Gói 3 Ngày - *30.000đ*\nLiên hệ: *@{CONFIG['ADMIN_USERNAME']}*",
        "buy_7day": f"Gói 7 Ngày - *50.000đ*\nLiên hệ: *@{CONFIG['ADMIN_USERNAME']}*",
        "buy_10day": f"Gói 10 Ngày - *90.000đ*\nLiên hệ: *@{CONFIG['ADMIN_USERNAME']}*",
        "buy_30day": f"Gói 30 Ngày - *170.000đ*\nLiên hệ: *@{CONFIG['ADMIN_USERNAME']}*",
        "vip_likes": f"*💖 CHI TIẾT GÓI LIKES*\n" \
                     f"💎 50K / 7 ngày — *700 Likes*\n" \
                     f"💎 60K / 14 ngày — *1400 Likes*\n" \
                     f"💎 170K / 30 ngày — *3000 Likes*\n" \
                     f"Liên hệ: *@{CONFIG['ADMIN_USERNAME']}*"
    }
    if query.data in packages:
        await query.edit_message_text(packages[query.data], parse_mode="Markdown")

# Main
async def main_async():
    try:
        app = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()
    except Exception:
        await notify_admin(None, "Lỗi khởi tạo bot")
        return
    
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("like", like_command))
    app.add_handler(CommandHandler("buy", buy_command))
    app.add_handler(CommandHandler("menuff", menuff_command))
    app.add_handler(CommandHandler("likeffvip", likeffvip_command))
    app.add_handler(CommandHandler("likefflai", likefflai_command))
    app.add_handler(CommandHandler("listvip", listvip_command))
    app.add_handler(CommandHandler("yes", yes_command))
    app.add_handler(CommandHandler("no", no_command))
    app.add_handler(CommandHandler("yes1", yes1_command))
    app.add_handler(CommandHandler("no1", no1_command))
    app.add_handler(CommandHandler("listgroups", listgroups_command))
    app.add_handler(CommandHandler("list_idad", list_idad_command))
    app.add_handler(CommandHandler("addadmin", add_admin_command))
    app.add_handler(CommandHandler("deladmin", deladmin_command))
    app.add_handler(CommandHandler("clearfiles", clearfiles_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        print("✅ Bot đã sẵn sàng - Gõ /admin để test!")
    except Exception:
        await notify_admin(app, "Lỗi khởi động bot")
        return
    
    try:
        # Chạy auto buff khởi động
        await perform_auto_buff(app, "KHỞI ĐỘNG")
        # Tạo các tác vụ bất đồng bộ
        asyncio.create_task(auto_buff_loop(app))
        asyncio.create_task(reload_vip_periodically(app))
        # Giữ bot chạy mãi mãi
        await asyncio.Event().wait()
    except Exception:
        await notify_admin(app, "Lỗi trong vòng lặp chính")
        await app.stop()
        await app.shutdown()

# Chạy bot
if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error running bot: {e}")