/* Extend jQuery with functions for PUT and DELETE requests. */

function _ajax_request(url, data, callback, type, method) {
    if (jQuery.isFunction(data)) {
        callback = data;
        data = {};
    }
    return jQuery.ajax({
        type: method,
        url: url,
        data: data,
        success: callback,
        dataType: type
        });
}

jQuery.extend({
    put: function(url, data, callback, type) {
        return _ajax_request(url, data, callback, type, 'PUT');
    },
    delete_: function(url, data, callback, type) {
        return _ajax_request(url, data, callback, type, 'DELETE');
    }
});

  $(function () {

    $(window).resize(function () {
        var h = Math.max($(window).height() - 0, 420);
        $('#container, #data, #tree, #data .content').height(h).filter('.default').css('lineHeight', h + 'px');
    }).resize();


    // 6 create an instance when the DOM is ready
    $('#tree').jstree({
        'core' : {
            'data' : {
                'url' : arvidapp.jstree,
                'data' : function (node) {
                    return { 'id' : node.id };
                }
            },
            'check_callback' : function(o, n, p, i, m) {
                if(m && m.dnd && m.pos !== 'i') { return false; }
                if(o === "move_node" || o === "copy_node") {
                    if(this.get_node(n).parent === this.get_node(p).id) { return false; }
                }
                return true;
            },
            'themes' : {
                'responsive' : false,
                'variant' : 'small',
                'stripes' : true
            }
        },
        'sort' : function(a, b) {
            return this.get_type(a) === this.get_type(b) ? (this.get_text(a) > this.get_text(b) ? 1 : -1) : (this.get_type(a) >= this.get_type(b) ? 1 : -1);
        },
        'contextmenu' : {
            'items' : function(node) {
                var tmp = $.jstree.defaults.contextmenu.items();
                delete tmp.ccp;
                delete tmp.edit;
                delete tmp.create;
                delete tmp.rename;

                tmp.set_as_input_file = {
                    label: "Use as input file",
                    action: function (data) {
                        var inst = $.jstree.reference(data.reference),
                        obj = inst.get_node(data.reference);
                        $('#input_file').val(obj.data.relpath);
                    },
                    seperator_after: false,
                    seperator_before: false
                };

                tmp.open_file = {
                    label: "Download",
                    action: function (data) {
                        var inst = $.jstree.reference(data.reference),
                        obj = inst.get_node(data.reference);
                        window.location = obj.data.file_op;
                    },
                    seperator_after: false,
                    seperator_before: false
                };

                return tmp;
            }
        },

        'types' : {
            'default' : { 'icon' : '/static/document.png' },
            'folder' : { 'icon' : '/static/folder.png' },
            'file' : { 'icon' : '/static/document.png' },
        },

        'unique' : {
            'duplicate' : function (name, counter) {
                return name + ' ' + counter;
            }
        },
        'plugins' : ['state','dnd','sort','types','contextmenu','unique']
    })
    .on('delete_node.jstree', function (e, data) {
        $.delete_(data.node.data.file_op)
            .fail(function () {
                data.instance.refresh();
            });
    })
    .on('delete_node.jstree', function (e, data) {
        $.delete_(data.node.data.file_op)
            .fail(function () {
                data.instance.refresh();
            });
    })
    .on('changed.jstree', function (e, data) {
        if (data && data.selected && data.selected.length && !data.node.data.directory) {
            $('#data .default').hide();
            $('#data .code').hide();
            $('#data .image').hide();
            if (data.node.data.display_mode === 'image') {
                $('#data .image img').one('load', function () {
                    $(this).css({'marginTop':'-' + $(this).height()/2 + 'px','marginLeft':'-' + $(this).width()/2 + 'px'});
                }).attr('src', data.node.data.file_op);
                $('#data .image').show();
            } else if (data.node.data.size < 10 * 1024 * 1024) {
                $.get(data.node.data.file_op, function (d) {
                    if (data.node.data.display_mode === 'image') {
                        $('#data .image img').one('load', function () {
                            $(this).css({'marginTop':'-' + $(this).height()/2 + 'px','marginLeft':'-' + $(this).width()/2 + 'px'});
                        }).attr('src',d);
                        $('#data .image').show();
                    } else if (data.node.data.display_mode === 'text') {
                        $('#data .code').show();
                        $('#code').text(d).attr('class', 'language-'+data.node.data.highlight).each(function(i, block) {
                            Prism.highlightElement(block);
                        });
                    } else {
                        $('#data .code').show();
                        $('#code').text('Cannot display file format');
                    }
                });
            } else {
                $('#data .code').show();
                $('#code').text('File too big');
            }
        } else {
            $('#data .content').hide();
            $('#data .default').html('Select a file from the tree.').show();
        }
    });
  });
