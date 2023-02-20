from discord.ext import commands
from discord import app_commands
from os import getenv
from dotenv import load_dotenv
import discord as dc
import requests as rq
import json
from discord.ui import Select, View
intents = dc.Intents.all()
intents.message_content = True
load_dotenv()

bot = commands.Bot(command_prefix='!', intents=intents)

# parameters
address = ''
code = ''
organizer = 0
items = {} # item = [option, ID, number_type, detail_dict, price]
count = 0
restaurant_name = ''
response = {}
#

def clear():
    global items, user_cost
    items = {}
    user_cost = {}

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} command(s)')
    except Exception as e:
        print(e)

async def check_permission(interaction, customer):
    global bot
    if interaction.user.id != customer:
        await interaction.response.send_message(f'只有 **{bot.get_user(customer).name}** 有權限選擇 !')
        return True
    else:
        return False

@app_commands.describe(input_address = '外送地址')
@bot.tree.command(name = 'addaddress')
async def addaddress(interact: dc.Interaction, input_address: str):
    global address, code, organizer, bot
    if address == '':
        address = input_address
        await interact.response.send_message('外送地址新增成功 !')
        organizer = interact.user.id
    elif interact.user.id != organizer:
        await interact.response.send_message(f'請詢問訂單發起者{bot.get_user(organizer).mention}，唯其可取消訂單')
    else:
        check = Select(
            placeholder = '確認更改地址 ? 訂單會全部消除 !',
            max_values = 1,
            min_values = 1,
            options = [
                dc.SelectOption(label = '是'),
                dc.SelectOption(label = '否')
            ]
        )
        view = View()
        view.add_item(check)
        msg = await interact.response.send_message(view = view)
        async def my_callback(interaction):
            if interaction.user.id != organizer:
                await interaction.response.send_message(f'請詢問訂單發起者{bot.get_user(organizer).mention}，唯其可取消訂單')
            global address
            if check.values[0][0] == '是':
                address = input_address
                await msg.delete()
                await interaction.response.send_message('更改地址成功 !')
                
            else :
                await msg.delete()
                await interaction.response.send_message('取消')
            
                
        check.callback = my_callback
        await msg.delete(delay = 120.0)
        

    

@app_commands.describe(input_name = '餐廳名稱')
@bot.tree.command(name = 'search')
async def search(interact: dc.Interaction, input_name: str):
    global address, organizer, count
    ctx = bot.get_channel(interact.channel_id)
    if address == '':
        await interact.response.send_message('請先輸入外送地址')
        return
    elif interact.user.id != organizer:
        await interact.response.send_message(f'請詢問訂單發起者{bot.get_user(organizer).mention}餐廳')
        return
    position = json.loads(rq.get('https://api.tomtom.com/search/2/geocode/' + address + '.json?key=' + getenv('TOMTOMAPIKEY') + '&countrySet=TW' + '&language=zh-TW').text)
    latitude = position['results'][0]['position']['lat']
    longtitude = position['results'][0]['position']['lon']
    headers = {'content-type': "application/json", "x-disco-client-id": "web"}
    response = json.loads(rq.get(f'https://disco.deliveryhero.io/listing/api/v1/pandora/search?query={input_name}&latitude={latitude}&longitude={longtitude}&configuration=Variation16&customer_id=&vertical=restaurants&search_vertical=restaurants&language_id=6&opening_type=delivery&session_id=&language_code=zh&customer_type=regular&limit=10&offset=0&country=tw&locale=zh_TW&use_free_delivery_label=false&tag_label_metadata=true&ncr_screen=NA%3ANA&ncr_place=search%3Alist', headers = headers).text)
    if response['data']['available_count'] == 0:
        await interact.response.send_message('你家太鄉下囉 ~ 沒有' + input_name)
        return 
    restaurant_list = response['data']['items']
    select = Select(
        placeholder = '選擇一個餐廳 !',
        max_values = 1,
        min_values = 1
    )
    for i in range(0, len(restaurant_list)):
        select.add_option(value = str(i), description = f'評價 {restaurant_list[i]["rating"]} 顆星, 外送{restaurant_list[i]["minimum_delivery_fee"]} 元以上, {restaurant_list[i]["minimum_delivery_time"]} 分鐘送達', label = restaurant_list[i]["name"]),

    async def my_callback(interaction):
        if await check_permission(interaction, organizer):
            return
        global code, count, restaurant_name
        if count != 0:
            await interaction.response.defer()
            check = Select(
                placeholder = '確認更改餐廳 ? 訂單會全部消除 !',
                max_values = 1,
                min_values = 1,
                options = [
                    dc.SelectOption(label = '是'),
                    dc.SelectOption(label = '否')
                ]
            )
            view2 = View()
            view2.add_item(check)
            msg = await ctx.send(view = view2)

            async def my_callback2(interaction2):
                if await check_permission(interaction2, organizer):
                    return
                global code, restaurant_name
                if check.values[0][0] == '是':
                    clear()
                    option = int(select.values[0])
                    restaurant_name = restaurant_list[option]['name']
                    code = restaurant_list[option]['code']
                    await interaction2.response.defer()
                    await msg.delete()
                    await ctx.send(f'更改餐廳為{restaurant_name} !')
                else :
                    await interaction2.response.defer()
                    await msg.delete()
                

            check.callback = my_callback2
            await msg.delete(delay = 120.0)

        else :
            count += 1
            option = int(select.values[0])
            restaurant_name = restaurant_list[option]['name']
            code = restaurant_list[option]['code']
            await interaction.response.send_message(f'你選擇： {restaurant_name}')

    select.callback = my_callback

    view = View()
    view.add_item(select)
    await interact.response.send_message(view = view)

@bot.tree.command(name = 'order')
async def order(interact: dc.Interaction):
    ctx = bot.get_channel(interact.channel_id)
    global response
    author = interact.user.id
    global code, items
    category_headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36 Edg/92.0.902.73'}
    url = 'https://tw.fd-api.com/api/v5/vendors/' + code + '?include=menus&language_id=6&dynamic_pricing=0&opening_type=delivery&basket_currency=TWD'
    response = json.loads(rq.get(url = url, headers = category_headers).text)
    category = response['data']['menus'][0]['menu_categories']
    select = Select(
        placeholder = '選擇一個餐點類別 !',
        max_values = 1,
        min_values = 1,
    )
    for i in range(0, len(category)) :
        select.add_option(value = i, label = category[i]["name"], description=f'{category[i]["description"][:99]}')
    
    async def my_callback(interaction):
        if await check_permission(interaction, author):
            return
        category = response['data']['menus'][0]['menu_categories']
        option = int(select.values[0])
        select2 = Select(
            max_values = 1,
            min_values = 0,
            placeholder = '選擇餐點 !',
        )
        products = category[option]['products']
        for i in range(0, len(products)) :
            select2.add_option(value = i, label = products[i]['name'], description = products[i]['description'][:99])
        
        view2 = View()
        view2.add_item(select2)

        await interaction.response.send_message(view = view2) 

        async def my_callback2(interaction2):
            if await check_permission(interaction2, author):
                return
            ID = int(select2.values[0])
            detail = products[ID]
            embed = dc.Embed(
                title = detail['name'],
                description = detail['description']
            )
            embed.set_thumbnail(url = detail['file_path'])
            await ctx.send(embed = embed)


            async def topping_choose(client, number_type):
                topping_ids = detail['product_variations'][number_type]['topping_ids']
                topping_description = response['data']['menus'][0]['toppings']
                detail_dict = []
                record = []
                for i in range(0, len(topping_ids)):
                    detail_dict.append([])
                    record.append(False)
                    cnt = [0]
                async def get_detail(topping_id, id, tot):
                    max_values = min(topping_description[topping_id]['quantity_maximum'], len(topping_description[topping_id]['options']))
                    min_values = topping_description[topping_id]['quantity_minimum']
                    select4 = Select(
                        placeholder = f'{topping_description[topping_id]["name"]} ( 請選 {min_values} ~ {max_values} 項 )',
                        max_values = max_values,
                        min_values = min_values
                    )
                    if min_values == 0:
                        select4.add_option(value = -1, label = '不選擇', description = 'FREE')
                    for i in range(0, len(topping_description[topping_id]['options'])):
                        extra = round(topping_description[topping_id]['options'][i]['price'])
                        select4.add_option(value = i, label = topping_description[topping_id]['options'][i]['name'], description = f'額外 ${extra}' if extra else 'FREE')
                    async def my_callback4(interaction4):
                        if await check_permission(interaction4, author):
                            return
                        if record[id] == False:
                            cnt[0] += 1
                        record[id] = True
                        detail_list = []
                        for i in range(0, len(select4.values)):
                            detail_list.append(select4.values[i])
                        detail_dict[id] = detail_list
                        if cnt[0] != tot:
                            await interaction4.response.defer()
                        else:
                            price = products[ID]['product_variations'][number_type]['price']
                            desn = ''
                            if len(products[ID]['product_variations']) > 1:
                                desn = products[ID]['product_variations'][number_type]['name'] + '  $' + str(round(products[ID]['product_variations'][number_type]['price']))
                            else :
                                desn = '$' + str(round(products[ID]['product_variations'][number_type]['price']))
                            embed = dc.Embed(
                                title = products[ID]['name'],
                                description = desn
                            )
                            extra = 0
                            for j in range(0, len(topping_ids)):
                                name = topping_description[str(topping_ids[j])]['name']
                                value = ''
                                money = 0
                                if detail_dict[j][0] == -1:
                                    value = '不選擇'
                                else:
                                    for k in range(0, len(detail_dict[j])):
                                        value += topping_description[str(topping_ids[j])]['options'][int(detail_dict[j][k])]['name']
                                        if k != len(detail_dict[j]) - 1:
                                            value += '  /  '
                                        money += topping_description[str(topping_ids[j])]['options'][int(detail_dict[j][k])]['price']
                                    
                                    if money != 0:
                                        value += '  $' + str(round(money))
                                    else:
                                        value += '  FREE'
                                    extra += money
                                    
                                embed.add_field(name = name, value = value, inline = True)
                            embed.add_field(name = '總價', value = str(round(price + extra)) + '元', inline = True)
                            await ctx.send(embed = embed)

                            select5 = Select(
                                placeholder = '加入購物車',
                                max_values = 1,
                                min_values = 1,
                                options = [
                                    dc.SelectOption(label = '是'),
                                    dc.SelectOption(label = '否')
                                ]
                            )
                            async def my_callback5(interaction5):
                                if await check_permission(interaction5, author):
                                    return
                                choose = select5.values[0]
                                if choose == '是':
                                    item = [option, ID, number_type, detail_dict, price + extra]
                                    if interact.user.id in items:
                                        items[interact.user.id].append(item)
                                    else:
                                        items[interact.user.id] = [item]
                                    await interaction5.response.send_message('成功 !')
                                else:
                                    await interaction5.response.send_message('取消')
                            select5.callback = my_callback5
                            view5 = View()
                            view5.add_item(select5)
                            await interaction4.response.send_message(view = view5)
                    
                    select4.callback = my_callback4
                    return select4

                tot_topping = 0
                for i in range(0, len(topping_ids)):
                    Range = topping_description[str(topping_ids[i])]
                    if not Range['quantity_minimum'] == Range['quantity_maximum'] == len(Range['options']):
                        tot_topping += 1

                if tot_topping != 0:
                    total_select = View()
                    for i in range(0, len(topping_ids)):
                        Range = topping_description[str(topping_ids[i])]
                        if Range['quantity_minimum'] == Range['quantity_maximum'] == len(Range['options']):
                            continue
                        select_tmp = await get_detail(str(topping_ids[i]), i, tot_topping)
                        total_select.add_item(select_tmp)
                    await client.response.send_message(view = total_select)  
                else:
                    desn = ''
                    if len(products[ID]['product_variations']) > 1:
                        desn = products[ID]['product_variations'][number_type]['name'] + '  $' + str(round(products[ID]['product_variations'][number_type]['price']))
                    else :
                        desn = '$' + str(round(products[ID]['product_variations'][number_type]['price']))
                    embed = dc.Embed(
                        title = products[ID]['name'],
                        description = desn
                    )
                    await ctx.send(embed = embed)
                    select5 = Select(
                        placeholder = '加入購物車',
                        max_values = 1,
                        min_values = 1,
                        options = [
                            dc.SelectOption(label = '是'),
                            dc.SelectOption(label = '否')
                        ]
                    )
                    async def my_callback5(interaction5):
                        if await check_permission(interaction5, author):
                            return
                        choose = select5.values[0]
                        if choose == '是':
                            item = [option, ID, number_type, detail_dict, products[ID]['product_variations'][number_type]['price']]
                            if interact.user.id in items:
                                items[interact.user.id].append(item)
                            else:
                                items[interact.user.id] = [item]
                            await interaction5.response.send_message('成功 !')
                        else:
                            await interaction5.response.send_message('取消')
                    select5.callback = my_callback5
                    view5 = View()
                    view5.add_item(select5)
                    await client.response.send_message(view = view5)



            if len(detail['product_variations']) != 1:
                select3 = Select(
                    max_values = 1,
                    min_values = 1,
                    placeholder = '選擇餐點項目 !',
                )
                for i in range(0, len(detail['product_variations'])):
                    select3.add_option(value = i, label = detail['product_variations'][i]['name'], description = '價格:' + str(round(detail['product_variations'][i]['price'])))
                
                async def my_callback3(interaction3):
                    if await check_permission(interaction3, author):
                        return
                    await topping_choose(interaction3, int(select3.values[0]))

                select3.callback = my_callback3
                view3 = View()
                view3.add_item(select3)
                await interaction2.response.send_message(view = view3)
                
            else:
                await topping_choose(interaction2, 0)

        select2.callback = my_callback2
        
    select.callback = my_callback
    view = View()
    view.add_item(select)
    await interact.response.send_message(view = view)

@bot.tree.command(name = 'get_name')
async def get_name(interact: dc.Interaction):
    global restaurant_name
    await interact.response.send_message(f'餐廳：{restaurant_name}')

@bot.tree.command(name = 'view')
async def view(interact: dc.Interaction):
    ctx = bot.get_channel(interact.channel_id)
    global items, response
    
    tot = 0
    
    goods = items[interact.user.id]
    for i in range(0, len(goods)):
        tot += goods[i][4]
    if tot == 0:
        await interact.response.send_message('您尚未購賣任何餐點 !')
        return
    embed = dc.Embed(
        title = '購物車品項',
    )
    for i in range(0, len(goods)):
        option, ID, number_type, detail_dict, price = goods[i]
        product = response['data']['menus'][0]['menu_categories'][option]['products'][ID]
        name = response['data']['menus'][0]['menu_categories'][option]['products'][ID]['name']
        tmp = response['data']['menus'][0]['menu_categories'][option]['products'][ID]['product_variations']
        if len(tmp) != 1:
            name += '  ' + tmp[number_type]['name']
        name += '  $' + str(round(price))
        value = ''
        
        topping_ids = product['product_variations'][number_type]['topping_ids']
        topping_description = response['data']['menus'][0]['toppings']
        for i in range(0, len(topping_ids)):
            topping_id = topping_ids[i]
            if topping_description[str(topping_id)]['quantity_maximum'] == topping_description[str(topping_id)]['quantity_minimum'] == len(topping_description[str(topping_id)]['options']):
                continue
            else:
                for j in range(0, len(detail_dict[i])):
                    string = ''
                    if int(detail_dict[i][j]) == -1:
                        string = '不選擇' + topping_description[str(topping_id)]['name']
                    else:
                        string = topping_description[str(topping_id)]['options'][int(detail_dict[i][j])]['name']
                    value += string
                    if j != len(detail_dict[i]) - 1:
                        value += ', '
                if i != len(topping_ids) - 1:
                    value += ' / '

        embed.add_field(name = name, value = value)
    await interact.response.send_message(embed = embed)

@bot.tree.command(name = 'edit')
async def edit(interact: dc.Interaction):
    ctx = bot.get_channel(interact.channel_id)
    global items, response
    goods = items[interact.user.id]
    select = Select(
        placeholder = '請選擇要更改餐點',
        max_values = 1,
        min_values = 1
    )
    for i in range(0, len(goods)):
        option, ID, number_type, detail_dict, price = goods[i] 
        product = response['data']['menus'][0]['menu_categories'][option]['products'][ID]
        description = f'${str(int(price))}'
        if len(product["product_variations"]) != 1:
            description += '  ' + product["product_variations"][number_type]["name"]
        select.add_option(value = i, label = product['name'], description = description)
    async def my_callback(interaction):
        if await check_permission(interaction, interact.user.id):
            return
        good = goods[int(select.values[0])]
        select2 = Select(
            placeholder = '請選擇要改變項目',
            min_values = 1,
            max_values = 1
        )
        option, ID, number_type, detail_dict, price = good
        product = response['data']['menus'][0]['menu_categories'][option]['products'][ID]['product_variations'][number_type]
        topping_description = response['data']['menus'][0]['toppings']
        cnt = 0
        for i in range(0, len(product['topping_ids'])):
            topping = topping_description[str(product['topping_ids'][i])]
            if not topping['quantity_minimum'] == topping['quantity_maximum'] == len(topping['options']):
                cnt += 1
                description = ''
                for j in range(0, len(detail_dict[i])):
                    description += topping['options'][int(detail_dict[i][j])]['name']
                    if j != len(detail_dict[i]) - 1:
                        description += '  /  '
                select2.add_option(value = i, label = topping['name'], description = description[:99])
        
        
        async def my_callback2(interaction2):
            if await check_permission(interaction2, interact.user.id):
                return
            id = int(select2.values[0])
            topping_id = product['topping_ids'][id]
            select3 = Select(
                placeholder = topping_description[str(topping_id)]['name'],
                max_values = min(topping_description[str(topping_id)]['quantity_maximum'], len(topping_description[str(topping_id)]['options'])),
                min_values = topping_description[str(topping_id)]['quantity_minimum']
            )
            detail_list = good[3][id]
            if topping_description[str(topping_id)]['quantity_minimum'] == 0:
                _default = (True if str(-1) in detail_list else False)
                select3.add_option(default = _default, value = -1, label = '不選擇  ' + topping_description[str(topping_id)]['name'], description = 'FREE')
            for i in range(0, len(topping_description[str(topping_id)]['options'])):
                label = topping_description[str(topping_id)]['options'][i]['name']
                price = topping_description[str(topping_id)]['options'][i]['price']
                description = 'FREE' if price == 0 else f'${str(round(price))}'
                _default = (True if str(i) in detail_list else False)
                select3.add_option(default = _default, value = i, label = label, description = description)
            
            async def my_callback3(interaction3):
                if await check_permission(interaction3, interact.user.id):
                    return
                detail_list = []
                cost = 0
                for i in range(0, len(detail_dict[int(select2.values[0])])):
                    cost -= topping_description[str(topping_id)]['options'][int(detail_dict[int(select2.values[0])][i])]['price']
                for i in range(0, len(select3.values)):
                    cost += topping_description[str(topping_id)]['options'][int(select3.values[i])]['price']
                    detail_list.append(select3.values[i])
                items[interact.user.id][int(select.values[0])][3][int(select2.values[0])] = detail_list
                items[interact.user.id][int(select.values[0])][4] += cost
                await interaction3.response.send_message('成功 !')


            select3.callback = my_callback3
            view3 = View()
            view3.add_item(select3)
            await interaction2.response.send_message(view = view3)
        select2.callback = my_callback2
        view2 = View()
        view2.add_item(select2)
        await interaction.response.send_message(view = view2)
    select.callback = my_callback
    view = View()
    view.add_item(select)
    await interact.response.send_message(view = view)

@bot.tree.command(name = 'delete')
async def delete(interact: dc.Interaction):
    ctx = bot.get_channel(interact.channel_id)
    global items, response
    goods = items[interact.user.id]
    select = Select(
        placeholder = '請選擇要刪除餐點',
        max_values = 1,
        min_values = 1
    )
    for i in range(0, len(goods)):
        option, ID, number_type, detail_dict, price = goods[i] 
        product = response['data']['menus'][0]['menu_categories'][option]['products'][ID]
        description = f'${str(int(price))}'
        if len(product["product_variations"]) != 1:
            description += '  ' + product["product_variations"][number_type]["name"]
        select.add_option(value = i, label = product['name'], description = description)
    async def my_callback(interaction):
        if await check_permission(interaction, interact.user.id):
            return
        id = int(select.values[0])
        del items[interact.user.id][id]
        await interaction.response.send_message('成功 !')
    select.callback = my_callback
    view = View()
    view.add_item(select)
    await interact.response.send_message(view = view)

@bot.tree.command(name = 'submit')
async def submit(interact: dc.Interaction):
    ctx = bot.get_channel(interact.channel_id)
    global items, response, organizer
    if interact.user.id != organizer:
        await ctx.send(f'只有 **{bot.get_user(organizer).name}** 有權限選擇 !')
        return
    embed = dc.Embed(
        title = '購物車'
    )
    for customer in items:
        name = bot.get_user(customer).name
        value = ''
        tot = 0
        for i in range(0, len(items[customer])):
            option, ID, number_type, detail_dict, price = items[customer][i]
            tot += price
            product = response['data']['menus'][0]['menu_categories'][option]['products'][ID]
            description = product['name'] + '  '
            if len(product['product_variations']) != 1:
                description += product['product_variations'][i]['name']
            value += description
            if i != len(items[customer]) - 1:
                value += '  /  '
        embed.add_field(name = name + '  $' + str(tot), value = value)
    await ctx.send(embed = embed)
    select = Select(
        placeholder = '確認送出 ?',
        options = [
            dc.SelectOption(label = '是'),
            dc.SelectOption(label = '否')
        ],
        max_values = 1,
        min_values = 1
    )
    async def my_callback(interaction):
        if await check_permission(interaction, organizer):
            return
        if select.values[0] == '是': 
            await interaction.response.send_message('成功 !')
        else:
            await interaction.response.send_message('取消 !')

    select.callback = my_callback
    view = View()
    view.add_item(select)
    await interact.response.send_message(view = view)

TOKEN = getenv('TOKEN')
bot.run(TOKEN)