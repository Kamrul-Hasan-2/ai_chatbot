import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.simple_chatbot_flow import ChatMode, SimpleChatbot


def test_ghori_maps_to_watch_keywords():
    bot = SimpleChatbot()

    assert bot._looks_like_product_query('ghori') is True
    assert bot._looks_like_product_query('hat ghori') is True

    assert bot._build_product_search_keywords('ghori') == 'watch'
    assert bot._build_product_search_keywords('hat ghori') == 'hand watch'


def test_konta_valo_triggers_comparison():
    bot = SimpleChatbot()

    assert bot._is_comparison_query('konta valo') is True


def test_konta_valo_process_message_returns_reply_in_agent_mode():
    bot = SimpleChatbot()
    bot._check_responder_type = lambda _user_id: 'agent'

    result = bot.process_message('user-1', 'konta valo')

    assert result['mode'] == 'ai'
    assert result['intent'] == 'product_comparison'
    assert 'আমাদের প্রতিটি প্রোডাক্টই ভালো' in result['response']


def test_create_response_includes_link_buttons_from_products():
    bot = SimpleChatbot()
    products = [
        {
            'title': 'Sample Product',
            'price': '1000',
            'url': 'https://www.bdstall.com/listingDetail/index/1234/'
        }
    ]

    result = bot._create_response(
        user_id='user-2',
        message='show product',
        response='product list',
        mode=ChatMode.AI,
        intent='product_search',
        products=products,
        processing_time=0.1
    )

    assert isinstance(result.get('link_buttons'), list)
    assert result['link_buttons']
    assert result['link_buttons'][0]['index'] == 1
    assert result['link_buttons'][0]['title'] == 'Sample Product'
    assert result['link_buttons'][0]['price'] == '1000'
    assert result['link_buttons'][0]['text'] == 'View this link'
    assert result['link_buttons'][0]['url'] == 'https://www.bdstall.com/listingDetail/index/1234/'