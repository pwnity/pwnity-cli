
from unittest.mock import MagicMock

def test_list_targets_empty(client, mock_cli):
    mock_cli.target_mgr.list_all.return_value = []
    
    resp = client.get('/api/targets/list')
    assert resp.status_code == 200
    assert resp.json == []

def test_list_targets_with_details(client, mock_cli):
    mock_cli.target_mgr.list_all.return_value = ['foo']
    mock_cli.target_mgr.load.return_value = {'name': 'foo', 'ip': '1.2.3.4'}
    
    resp = client.get('/api/targets/list?details=true')
    assert resp.status_code == 200
    assert len(resp.json) == 1
    assert resp.json[0]['name'] == 'foo'
    assert resp.json[0]['ip'] == '1.2.3.4'

def test_create_target_simple(client, mock_cli):
    mock_cli.target_mgr.exists.return_value = False
    mock_cli.target_mgr.create.return_value = True
    
    resp = client.post('/api/item/target', json={'name': 'new-target'})
    
    assert resp.status_code == 200
    assert resp.json['success'] is True
    mock_cli.target_mgr.create.assert_called_with('new-target')

def test_create_target_with_url(client, mock_cli):
    mock_cli.target_mgr.exists.return_value = False
    mock_cli.target_mgr.create.return_value = True
    
    # We must ensure _parse_and_update_from_url exists on the mock
    # Since MagicMock creates attributes on access, it should be fine,
    # but let's be explicit if we want to assert on it.
    
    resp = client.post('/api/item/target', json={'name': 'google', 'url': 'https://google.com'})
    
    assert resp.status_code == 200
    mock_cli.target_mgr.create.assert_called_with('google')
    mock_cli.target_mgr._parse_and_update_from_url.assert_called()
    args = mock_cli.target_mgr._parse_and_update_from_url.call_args
    assert args[0][0] == 'google'
    assert args[0][1] == 'https://google.com'

def test_update_target_url(client, mock_cli):
    # This tests the manage_item_details route logic for URL updates
    mock_cli.target_mgr.update.return_value = {'name': 'foo'} # specific return doesn't matter much for this test unless we check it
    
    # Mock load to return something so the final load() call succeeds
    mock_cli.target_mgr.load.return_value = {'name': 'foo', 'url': 'https://foo.com'}

    resp = client.post('/api/details/target/foo', json={
        'key': 'url',
        'value': 'https://foo.com'
    })
    
    assert resp.status_code == 200
    # Should call _parse_and_update_from_url instead of update
    mock_cli.target_mgr._parse_and_update_from_url.assert_called_with('foo', 'https://foo.com', mock_cli)
    # And then load
    mock_cli.target_mgr.load.assert_called_with('foo')

def test_delete_target(client, mock_cli):
    mock_cli.target_mgr.destroy.return_value = True
    
    resp = client.delete('/api/item/target/old-target')
    
    assert resp.status_code == 200
    assert resp.json['success'] is True
    mock_cli.target_mgr.destroy.assert_called_with('old-target')
