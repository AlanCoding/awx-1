import React, { useCallback } from 'react';
import { useField, useFormikContext } from 'formik';
import { t, Trans } from '@lingui/macro';
import CredentialLookup from '../../../../components/Lookup/CredentialLookup';
import {
  OptionsField,
  SourceVarsField,
  VerbosityField,
  EnabledVarField,
  EnabledValueField,
  HostFilterField,
} from './SharedFields';
import { required } from '../../../../util/validators';
import getDocsBaseUrl from '../../../../util/getDocsBaseUrl';
import { useConfig } from '../../../../contexts/Config';

const VMwareSubForm = ({ autoPopulateCredential }) => {
  const { setFieldValue, setFieldTouched } = useFormikContext();
  const [credentialField, credentialMeta, credentialHelpers] = useField(
    'credential'
  );
  const config = useConfig();

  const handleCredentialUpdate = useCallback(
    value => {
      setFieldValue('credential', value);
      setFieldTouched('credential', true, false);
    },
    [setFieldValue, setFieldTouched]
  );

  const pluginLink = `${getDocsBaseUrl(
    config
  )}/html/userguide/inventories.html#inventory-plugins`;
  const configLink =
    'https://docs.ansible.com/ansible/latest/collections/community/vmware/vmware_vm_inventory_inventory.html';

  return (
    <>
      <CredentialLookup
        credentialTypeNamespace="vmware"
        label={t`Credential`}
        helperTextInvalid={credentialMeta.error}
        isValid={!credentialMeta.touched || !credentialMeta.error}
        onBlur={() => credentialHelpers.setTouched()}
        onChange={handleCredentialUpdate}
        value={credentialField.value}
        required
        autoPopulate={autoPopulateCredential}
        validate={required(t`Select a value for this field`)}
      />
      <VerbosityField />
      <HostFilterField />
      <EnabledVarField />
      <EnabledValueField />
      <OptionsField />
      <SourceVarsField
        popoverContent={
          <>
            <Trans>
              Enter variables to configure the inventory source. For a detailed
              description of how to configure this plugin, see{' '}
              <a href={pluginLink} target="_blank" rel="noopener noreferrer">
                Inventory Plugins
              </a>{' '}
              in the documentation and the{' '}
              <a href={configLink} target="_blank" rel="noopener noreferrer">
                vmware_vm_inventory
              </a>{' '}
              plugin configuration guide.
            </Trans>
            <br />
            <br />
          </>
        }
      />
    </>
  );
};

export default VMwareSubForm;
