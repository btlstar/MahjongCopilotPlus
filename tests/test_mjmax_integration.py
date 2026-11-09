# Modified for MahjongCopilotPlus on 2026-11-03; see NOTICE.md.
"""Offline regression checks using real current Majsoul protobuf frames."""
import hashlib
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import liqi
from mitmproxy.websocket import WebSocketMessage
from ruamel.yaml import YAML

from mjmax import runtime
from mjmax.paths import CONFIG, PROTO
from mjmax.plugin import mod, data_update
from mjmax.proto import liqi_pb2 as pb, basic_pb2


def frame(kind, method, payload, msg_id=1):
    envelope = basic_pb2.BaseMessage()
    envelope.method_name = '' if kind == 3 else method
    envelope.data = payload.SerializeToString()
    return bytes([kind]) + (b'' if kind == 1 else struct.pack('<H', msg_id)) + envelope.SerializeToString()


def body(content, cls):
    envelope = basic_pb2.BaseMessage.FromString(content[1:] if content[0] == 1 else content[3:])
    return cls.FromString(envelope.data)


class ModIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        temp_config = Path(self.tmp.name)
        shutil.copy2(CONFIG / 'max_data.yaml', temp_config / 'max_data.yaml')
        (temp_config / 'settings.mod.yaml').write_text(
            'config:\n  character: 200001\n  characters: {200001: 400101}\n  show_server: false\n', encoding='utf-8')
        self.addCleanup(patch.stopall)
        patch.object(mod, 'CONFIG', temp_config).start()
        patch.object(runtime, 'load_settings', return_value={
            'plugin_enable': {'mod': True},
            'liqi': {'auto_update': False},
        }).start()
        self.injected = []
        patch.object(runtime.ctx, 'master', SimpleNamespace(commands=SimpleNamespace(
            call=lambda *args: self.injected.append(args))), create=True).start()
        self.addon = runtime.ModAddon()
        self.plugin = self.addon.mod_plugin
        self.snapshot = json.loads((CONFIG / 'data_version.json').read_text(encoding='utf-8'))
        self.flow = self.new_flow('lobby')
        self.next_id = 1

    def new_flow(self, flow_id):
        flow = SimpleNamespace(id=flow_id, request=SimpleNamespace(path='/', pretty_url='https://game.maj-soul.com/'),
                               websocket=SimpleNamespace(messages=[]))
        self.addon.websocket_start(flow)
        return flow

    def send(self, content, from_client, flow=None):
        flow = flow or self.flow
        message = WebSocketMessage(2, from_client, content)
        flow.websocket.messages.append(message)
        self.addon.websocket_message(flow)
        return message

    def exchange(self, method, response, request=None):
        msg_id = self.next_id
        self.next_id += 1
        if request is None:
            request = getattr(pb, pb.RPC_METHODS[method]['req'].rsplit('.', 1)[-1])()
        self.send(frame(2, method, request, msg_id), True)
        return self.send(frame(3, method, response, msg_id), False)

    def login(self):
        response = pb.ResLogin(account_id=123456)
        response.account.account_id = 123456
        response.account.nickname = 'original'
        response.account.avatar_id = 400101
        return self.exchange('.lq.Lobby.login', response)

    def test_latest_snapshot_matches_manifest(self):
        manifest = json.loads((CONFIG / 'data_version.json').read_text(encoding='utf-8'))
        for name, path in data_update.FILES.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), manifest['sha256'][name])
        self.assertEqual(len(self.plugin.max_data['skin']), manifest['counts']['skin'])
        self.assertEqual(len(self.plugin.max_data['character']), manifest['counts']['character'])
        self.assertEqual(pb.RPC_METHODS, json.loads((PROTO / 'liqi.json').read_text(encoding='utf-8')))

    def test_login_and_combined_web_info(self):
        self.login()
        self.assertEqual(self.plugin.safe['account_id'], 123456)
        response = pb.ResFetchInfo()
        response.character_info.main_character_id = 200001
        response.character_info.characters.add(charid=200001, skin=400101, exp=77)
        response.bag_info.bag.items.add(item_id=99999999, stack=17)
        message = self.exchange('.lq.Lobby.fetchInfo', response)
        result = body(message.content, pb.ResFetchInfo)
        self.assertEqual(list(result.character_info.skins), self.plugin.max_data['skin'])
        self.assertEqual(len(result.character_info.characters), self.snapshot['counts']['character'])
        self.assertEqual(self.plugin.safe['characters'][0].exp, 77)
        self.assertEqual(self.plugin.safe['items'][0].item_id, 99999999)
        self.assertTrue(any(i.item_id == 99999999 and i.stack == 17 for i in result.bag_info.bag.items))
        self.assertEqual(list(result.title_list.title_list), self.plugin.max_data['title'])

    def test_character_info_with_new_characters_and_missing_emoji(self):
        self.plugin.settings['config']['emoji'] = True
        response = pb.ResCharacterInfo(main_character_id=200001)
        response.characters.add(charid=200001, skin=400101, exp=42)
        result = body(self.exchange('.lq.Lobby.fetchCharacterInfo', response).content, pb.ResCharacterInfo)
        self.assertEqual(len(result.characters), self.snapshot['counts']['character'])
        self.assertEqual(len(result.skins), self.snapshot['counts']['skin'])
        self.assertEqual(self.plugin.safe['characters'][0].exp, 42)
        self.assertTrue(all(c.skin in result.skins for c in result.characters))

    def test_skin_change_is_local_and_injects_new_skin(self):
        self.login()
        self.send(frame(2, '.lq.Lobby.loginBeat', pb.ReqLoginBeat(contract='contract'), 20), True)
        character = self.plugin.max_data['character'][-1]
        skin = self.plugin.settings['config']['characters'][character]
        message = self.send(frame(2, '.lq.Lobby.changeCharacterSkin',
                                  pb.ReqChangeCharacterSkin(character_id=character, skin=skin), 21), True)
        envelope = basic_pb2.BaseMessage.FromString(message.content[3:])
        self.assertEqual(envelope.method_name, '.lq.Lobby.loginBeat')
        self.assertEqual(body(message.content, pb.ReqLoginBeat).contract, 'contract')
        injected = body(self.injected[-1][3], pb.NotifyAccountUpdate)
        self.assertEqual(injected.update.character.characters[0].skin, skin)
        self.send(frame(3, '', pb.ResCommon(), 21), False)
        self.assertNotIn(21, self.addon.parsers['lobby'].res_type)

    def room_player_fixture(self, account_id=123456):
        player = pb.PlayerGameView(account_id=account_id,avatar_id=400101,nickname='original')
        player.character.charid, player.character.skin = 200001, 400101
        player.character.exp, player.character.level = 123, 2
        player.character.rewarded_level.extend([1,2])
        return player

    def select_room_character(self):
        self.plugin.settings['config']['character'] = 200002
        self.plugin.settings['config']['characters'][200002] = 400201

    def assert_room_identity(self, player):
        self.assertEqual(player.avatar_id,400201)
        self.assertEqual(player.character.charid,200002)
        self.assertEqual(player.character.skin,400201)
        self.assertEqual(list(player.character.rewarded_level),[1,2,3,4,5])

    def test_room_updates_keep_character_and_avatar_consistent(self):
        self.login()
        self.select_room_character()
        response = pb.NotifyRoomPlayerUpdate(owner_id=123456,seq=7,robot_count=1)
        response.player_list.add().CopyFrom(self.room_player_fixture())
        peer = response.player_list.add()
        peer.CopyFrom(self.room_player_fixture(456789))
        peer_before = peer.SerializeToString()
        response.positions.extend([0,1])
        message = self.send(frame(1,'.lq.NotifyRoomPlayerUpdate',response),False)
        result = body(message.content,pb.NotifyRoomPlayerUpdate)
        self.assert_room_identity(result.player_list[0])
        self.assertEqual(result.player_list[1].SerializeToString(),peer_before)
        self.assertEqual((result.owner_id,result.seq,result.robot_count),(123456,7,1))
        self.assertEqual(list(result.positions),[0,1])

    def test_create_join_and_fetch_room_share_the_selected_character(self):
        self.login()
        self.select_room_character()
        for method, cls in (('createRoom',pb.ResCreateRoom),('joinRoom',pb.ResJoinRoom),('fetchRoom',pb.ResSelfRoom)):
            with self.subTest(method=method):
                response = cls()
                response.room.room_id, response.room.seq = 54321, 9
                response.room.persons.add().CopyFrom(self.room_player_fixture())
                response.room.persons.add().CopyFrom(self.room_player_fixture(456789))
                other = response.room.persons[1].SerializeToString()
                result = body(self.exchange('.lq.Lobby.'+method,response).content,cls)
                self.assert_room_identity(result.room.persons[0])
                self.assertEqual(result.room.persons[1].SerializeToString(),other)
                self.assertEqual((result.room.room_id,result.room.seq),(54321,9))

    def test_room_ready_notification_is_not_changed_or_faked(self):
        self.login()
        ready = pb.NotifyRoomPlayerReady(account_id=123456,ready=True,seq=12)
        raw = frame(1,'.lq.NotifyRoomPlayerReady',ready)
        self.assertEqual(self.send(raw,False).content,raw)
        self.assertEqual(self.injected,[])

    def test_room_character_rewrite_preserves_unknown_protobuf_fields(self):
        self.login()
        self.select_room_character()
        response = pb.NotifyRoomPlayerUpdate()
        player = response.player_list.add()
        player.CopyFrom(self.room_player_fixture())
        unknown = b'\xa0\x06\x07'  # Future Character field 100.
        player.character.ParseFromString(player.character.SerializeToString()+unknown)
        result = body(self.send(frame(1,'.lq.NotifyRoomPlayerUpdate',response),False).content,pb.NotifyRoomPlayerUpdate)
        self.assert_room_identity(result.player_list[0])
        self.assertIn(unknown,result.player_list[0].character.SerializeToString())

    def test_room_with_unknown_account_does_not_rewrite_zero_account(self):
        self.select_room_character()
        response = pb.NotifyRoomPlayerUpdate()
        response.player_list.add().CopyFrom(self.room_player_fixture(0))
        expected = response.player_list[0].SerializeToString()
        result = body(self.send(frame(1,'.lq.NotifyRoomPlayerUpdate',response),False).content,pb.NotifyRoomPlayerUpdate)
        self.assertEqual(result.player_list[0].SerializeToString(),expected)

    def test_room_safe_mode_preserves_own_selected_character(self):
        self.login()
        self.select_room_character()
        self.plugin.settings['config']['safe_mode'] = True
        response = pb.NotifyRoomPlayerUpdate()
        response.player_list.add().CopyFrom(self.room_player_fixture())
        peer = response.player_list.add(account_id=456789,avatar_id=400301)
        peer.character.charid,peer.character.skin = 200003,400301
        result = body(self.send(frame(1,'.lq.NotifyRoomPlayerUpdate',response),False).content,pb.NotifyRoomPlayerUpdate)
        self.assert_room_identity(result.player_list[0])
        self.assertEqual((result.player_list[1].character.charid,result.player_list[1].character.skin),(200001,400101))

    def test_failed_server_response_is_not_rewritten(self):
        response = pb.ResLogin()
        response.error.code = 1001
        expected = frame(3, '', response)
        self.send(frame(2, '.lq.Lobby.login', pb.ReqLogin()), True)
        message = self.send(expected, False)
        self.assertEqual(message.content, expected)
        self.assertEqual(self.plugin.safe['account_id'], 0)

    def test_request_ids_are_independent_per_websocket(self):
        game = self.new_flow('game')
        self.send(frame(2, '.lq.Lobby.fetchCharacterInfo', pb.ReqCommon(), 7), True)
        self.send(frame(2, '.lq.FastTest.checkNetworkDelay', pb.ReqCommon(), 7), True, game)
        self.send(frame(3, '', pb.ResCommon(), 7), False, game)
        result = body(self.send(frame(3, '', pb.ResCharacterInfo(), 7), False).content, pb.ResCharacterInfo)
        self.assertEqual(len(result.skins), self.snapshot['counts']['skin'])
        self.addon.websocket_end(game)
        self.assertNotIn('game', self.addon.parsers)

    def test_auth_game_and_replay_keep_selected_skin(self):
        self.login()
        self.plugin.settings['config']['safe_mode'] = True
        self.plugin.settings['config']['character'] = self.plugin.max_data['character'][-1]
        selected = self.plugin.settings['config']['characters'][self.plugin.settings['config']['character']]
        response = pb.ResAuthGame()
        response.players.add(account_id=123456)
        response.players.add(account_id=654321)
        result = body(self.exchange('.lq.FastTest.authGame', response).content, pb.ResAuthGame)
        self.assertEqual(result.players[0].character.skin, selected)
        self.assertEqual(result.players[1].character.skin, 400101)
        record = pb.ResGameRecord()
        record.head.uuid = 'example-1234'
        record.head.accounts.add(account_id=123456, seat=0)
        record.head.accounts.add(account_id=654321, seat=1)
        result = body(self.exchange('.lq.Lobby.fetchGameRecord', record).content, pb.ResGameRecord)
        self.assertEqual(result.head.accounts[0].character.skin, selected)
        self.assertEqual(result.head.accounts[1].character.skin, 400101)

    def test_copilot_receives_original_frames(self):
        from mitm import WSDataInterceptor
        self.login()
        response = pb.ResAuthGame()
        response.players.add(account_id=123456)
        self.send(frame(2, '.lq.FastTest.authGame', pb.ReqAuthGame(), 30), True)
        raw = frame(3, '', response, 30)
        message = WebSocketMessage(2, False, raw)
        self.flow.websocket.messages.append(message)
        interceptor = WSDataInterceptor()
        interceptor.websocket_message(self.flow)
        self.addon.websocket_message(self.flow)
        self.assertEqual(interceptor.message_queue.get_nowait().content, raw)
        self.assertNotEqual(message.content, raw)

    def test_current_actions_remain_compatible_with_copilot(self):
        parser = liqi.LiqiProto()
        raw = parser.compose_notify({'type': liqi.MsgType.NOTIFY, 'method': '.lq.ActionPrototype',
            'data': {'name': 'ActionNewRound', 'step': 0, 'data': {'chang': 0, 'ju': 0,
                'tiles': ['1m'] * 13, 'sha256': 'a' * 64}}})
        decoded = parser.parse(raw)
        self.assertEqual(decoded['data']['data']['tiles'], ['1m'] * 13)
        self.assertEqual(decoded['data']['data']['sha256'], 'a' * 64)

    def test_current_actions_reach_existing_game_state(self):
        from game.game_state import GameState
        received = []
        bot = SimpleNamespace(init_bot=lambda *args: None,
                              react=lambda message: received.append(message),
                              react_batch=lambda messages: received.extend(messages))
        state = GameState(bot)
        parser = liqi.LiqiProto()
        state.input(parser.parse(frame(2, '.lq.FastTest.authGame', pb.ReqAuthGame(account_id=123456))))
        response = pb.ResAuthGame(seat_list=[123456, 2, 3, 4])
        response.game_config.meta.mode_id = 2
        state.input(parser.parse(frame(3, '', response)))
        raw = parser.compose_notify({'type': liqi.MsgType.NOTIFY, 'method': '.lq.ActionPrototype',
            'data': {'name': 'ActionNewRound', 'step': 0, 'data': {'chang': 0, 'ju': 0,
                'tiles': ['1m', '2m', '3m', '4m', '5m', '6m', '7m', '8m', '9m', '1p', '2p', '3p', '4p', '5p'],
                'doras': ['1s'], 'scores': [25000] * 4, 'sha256': 'a' * 64,
                'operation': {'seat': 0, 'operationList': [{'type': 1}]}}}})
        state.input(parser.parse(raw))
        self.assertEqual([m['type'] for m in received], ['start_game', 'start_kyoku', 'tsumo'])
        self.assertEqual(state.get_game_info().self_seat, 0)

    def test_migrates_existing_user_preferences_in_temporary_copy(self):
        original = {'config': {
            'character': 200001, 'characters': {200001: 400101},
            'nickname': 'offline-test', 'title': 600001, 'star_chars': [200001],
            'views': {0: [{'slot': 0, 'item_id': 305001}]}, 'views_index': 0,
            'loading_image': [250001],
            'random_character': {'enabled': True, 'pool': [400101]},
        }}
        target = Path(self.tmp.name) / 'settings.mod.yaml'
        with target.open('w', encoding='utf-8') as stream:
            YAML().dump(original, stream)
        migrated = mod.mod('test').settings['config']
        for key in ('character', 'nickname', 'title', 'star_chars', 'views', 'views_index',
                    'loading_image', 'random_character'):
            self.assertEqual(migrated[key], original['config'][key], key)

    def test_unknown_frames_and_observer_passthrough(self):
        raw = frame(2, '.lq.Lobby.futureMethod', pb.ReqCommon(), 50)
        self.assertEqual(self.send(raw, True).content, raw)
        self.flow.request.path = '/ob'
        self.assertEqual(self.send(b'not-protobuf', False).content, b'not-protobuf')


class UpdaterTests(unittest.TestCase):
    def test_reject_invalid_data_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'max_data.yaml'
            target.write_bytes(b'original')
            responses = [SimpleNamespace(raise_for_status=lambda: None, json=lambda: {
                'tag_name': 'next', 'assets': [
                    {'name': 'max_data.yaml', 'browser_download_url': 'https://example.com/data'},
                    {'name': 'liqi.desc', 'browser_download_url': 'https://example.com/proto'}]}),
                SimpleNamespace(raise_for_status=lambda: None, content=b'<html>error</html>'),
                SimpleNamespace(raise_for_status=lambda: None, content=b'invalid')]
            with patch.object(data_update, 'FILES', {'max_data.yaml': target, 'liqi.desc': Path(tmp) / 'liqi.desc'}), \
                 patch.object(data_update.requests, 'get', side_effect=responses):
                with self.assertRaises(ValueError):
                    data_update.update(force=True)
            self.assertEqual(target.read_bytes(), b'original')

    def test_install_rolls_back_on_partial_write_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / name for name in ('one', 'two')]
            for path in paths:
                path.write_bytes(b'old')
            replace = data_update.os.replace
            def fail_second(source, dest):
                if dest == paths[1]:
                    raise OSError('simulated write failure')
                return replace(source, dest)
            with patch.object(data_update.os, 'replace', side_effect=fail_second):
                with self.assertRaises(OSError):
                    data_update._install({path: b'new' for path in paths})
            self.assertTrue(all(path.read_bytes() == b'old' for path in paths))


if __name__ == '__main__':
    unittest.main()
