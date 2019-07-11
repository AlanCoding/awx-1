import logging
from time import time

from awx.main.fields import update_role_parentage_for_role
from awx.main.models.rbac import Role, batch_role_ancestor_rebuilding

logger = logging.getLogger('rbac_migrations')


def create_roles(apps, schema_editor):
    '''
    Implicit role creation happens in our post_save hook for all of our
    resources. Here we iterate through all of our resource types and call
    .save() to ensure all that happens for every object in the system.

    This can be used whenever new roles are introduced in a migration to
    create those roles for pre-existing objects that did not previously
    have them created via signals.
    '''

    models = [
        apps.get_model('main', m) for m in [
            'Organization',
            'Team',
            'Inventory',
            'Project',
            'Credential',
            'CustomInventoryScript',
            'JobTemplate',
        ]
    ]

    with batch_role_ancestor_rebuilding():
        for model in models:
            for obj in model.objects.iterator():
                obj.save()


def delete_all_user_roles(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', "ContentType")
    Role = apps.get_model('main', "Role")
    User = apps.get_model('auth', "User")
    user_content_type = ContentType.objects.get_for_model(User)
    for role in Role.objects.filter(content_type=user_content_type).iterator():
        role.delete()


def rebuild_role_hierarchy(apps, schema_editor):
    '''
    This should be called in any migration when ownerships are changed.
    Ex. I remove a user from the admin_role of a credential.
    Ancestors are cached from parents for performance, this re-computes ancestors.
    '''
    logger.info('Computing role roots..')
    start = time()
    roots = Role.objects \
                .all() \
                .values_list('id', flat=True)
    stop = time()
    logger.info('Found %d roots in %f seconds, rebuilding ancestry map' % (len(roots), stop - start))
    start = time()
    Role.rebuild_role_ancestor_list(roots, [])
    stop = time()
    logger.info('Rebuild completed in %f seconds' % (stop - start))
    logger.info('Done.')


def rebuild_role_parentage(apps, schema_editor):
    '''
    This should be called in any migration when any parent_role entry
    is modified so that the cached parent fields will be updated. Ex:
        foo_role = ImplicitRoleField(
            parent_role=['bar_role']  # change to parent_role=['admin_role']
        )

    This is like rebuild_role_hierarchy, but that method updates ancestors,
    whereas this method updates parents.
    '''
    print('entered method')
    Role = apps.get_model('main', "Role")
    updated_parents_ct = 0
    for role in Role.objects.iterator():
        print('role {}'.format(role))
        # The GenericForeignKey seems to like to deadlock if used as role.content_object
        # so we get the model from the migration
        ct = role.content_type
        app = 'main'
        if ct.lower() == 'user':
            app = 'auth'
        ct_model = apps.get_model(app, ct.model)
        try:
            content_object = ct_model.objects.get(pk=role.object_id)
        except ct_model.DoesNotExist:
            continue
        field = content_object._meta.get_field(role.role_field)
        changed = update_role_parentage_for_role(role, field)
        if changed:
            updated_parents_ct += 1
            logger.debug('Modified parentage for role {}'.format(role))
    if updated_parents_ct:
        logger.info('Updated parentage for {} roles'.format(updated_parents_ct))
    rebuild_role_hierarchy()
