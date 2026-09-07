import { useEffect, useMemo, useState } from 'react';
import type { ChoiceGroupResponse } from '../api/contracts';
import { formatQuantity } from '../utils/formatters';

export interface ConfiguredProductSelection {
  product_id: number;
  groups: Array<{
    group_id: number;
    option_ids: number[];
  }>;
}

function selectionGuidance(group: ChoiceGroupResponse): string {
  if (group.max_selections === 1) {
    return group.min_selections > 0 ? 'Elige 1 opción' : 'Elige una opción si lo deseas';
  }
  if (group.min_selections === group.max_selections) {
    return `Elige ${group.min_selections} opciones`;
  }
  if (group.min_selections > 0) {
    return `Elige entre ${group.min_selections} y ${group.max_selections} opciones`;
  }
  return `Elige hasta ${group.max_selections} opciones`;
}

function countIsComplete(group: ChoiceGroupResponse, count: number): boolean {
  return count >= group.min_selections && count <= group.max_selections;
}

interface ProductConfigurationProps {
  productId: number;
  groups: ChoiceGroupResponse[];
  disabled?: boolean;
  onSelectionChange?: (selection: ConfiguredProductSelection, ready: boolean) => void;
}

export function ProductConfiguration({ productId, groups, disabled = false, onSelectionChange }: ProductConfigurationProps) {
  const [selectedByGroup, setSelectedByGroup] = useState<Record<number, number[]>>({});

  const selection = useMemo<ConfiguredProductSelection>(() => ({
    product_id: productId,
    groups: groups.map((group) => ({
      group_id: group.id,
      option_ids: selectedByGroup[group.id] ?? [],
    })),
  }), [groups, productId, selectedByGroup]);

  const incompleteGroups = groups.filter((group) => {
    const selected = selection.groups.find((value) => value.group_id === group.id)?.option_ids ?? [];
    return !countIsComplete(group, selected.length);
  });
  const configurationReady = incompleteGroups.length === 0;

  useEffect(() => {
    onSelectionChange?.(selection, configurationReady);
  }, [configurationReady, onSelectionChange, selection]);

  const selectSingle = (groupId: number, optionId: number | null) => {
    setSelectedByGroup((current) => ({ ...current, [groupId]: optionId === null ? [] : [optionId] }));
  };

  const toggleMultiple = (group: ChoiceGroupResponse, optionId: number) => {
    setSelectedByGroup((current) => {
      const selected = current[group.id] ?? [];
      if (selected.includes(optionId)) {
        return { ...current, [group.id]: selected.filter((value) => value !== optionId) };
      }
      if (selected.length >= group.max_selections) return current;
      return { ...current, [group.id]: [...selected, optionId] };
    });
  };

  return (
    <section className="product-configuration" aria-labelledby="configuration-title">
      <header className="product-configuration-heading">
        <div>
          <p className="panel-kicker">A tu gusto</p>
          <h2 id="configuration-title">Personaliza tu elección</h2>
          <p>Selecciona las opciones que prefieras. El restaurante confirmará la configuración al pedir.</p>
        </div>
        <span className={`configuration-progress${configurationReady ? ' configuration-progress--ready' : ''}`}>
          {configurationReady ? 'Lista' : `${incompleteGroups.length} ${incompleteGroups.length === 1 ? 'pendiente' : 'pendientes'}`}
        </span>
      </header>

      <div className="product-configuration-groups">
        {groups.map((group) => {
          const selected = selectedByGroup[group.id] ?? [];
          const complete = countIsComplete(group, selected.length);
          const singleChoice = group.max_selections === 1;
          const guidanceId = `choice-group-${group.id}-guidance`;
          const statusId = `choice-group-${group.id}-status`;

          return (
            <fieldset
              className={`choice-group${!complete ? ' choice-group--incomplete' : ''}`}
              key={group.id}
              aria-describedby={`${guidanceId} ${statusId}`}
            >
              <legend>{group.name}</legend>
              <div className="choice-group-meta">
                <span className={`choice-requirement${group.required ? ' choice-requirement--required' : ''}`}>
                  {group.required ? 'Obligatorio' : 'Opcional'}
                </span>
                <span id={guidanceId}>{selectionGuidance(group)}</span>
              </div>

              <div className="choice-options">
                {singleChoice && !group.required && (
                  <label className={`choice-option${selected.length === 0 ? ' choice-option--selected' : ''}`}>
                    <input
                      type="radio"
                      name={`choice-group-${group.id}`}
                      checked={selected.length === 0}
                      disabled={disabled}
                      onChange={() => selectSingle(group.id, null)}
                    />
                    <span className="choice-option-copy">
                      <strong>Sin selección</strong>
                      <small>No agregar una opción de este grupo</small>
                    </span>
                  </label>
                )}

                {group.options.map((option) => {
                  const checked = selected.includes(option.id);
                  const atMaximum = !singleChoice && selected.length >= group.max_selections;
                  return (
                    <label className={`choice-option${checked ? ' choice-option--selected' : ''}${atMaximum && !checked ? ' choice-option--disabled' : ''}`} key={option.id}>
                      <input
                        type={singleChoice ? 'radio' : 'checkbox'}
                        name={`choice-group-${group.id}`}
                        checked={checked}
                        disabled={disabled || (atMaximum && !checked)}
                        onChange={() => singleChoice ? selectSingle(group.id, option.id) : toggleMultiple(group, option.id)}
                      />
                      <span className="choice-option-copy">
                        <strong>{option.name}</strong>
                        {option.description && <span>{option.description}</span>}
                        <small>Cantidad {formatQuantity(option.quantity)}</small>
                      </span>
                    </label>
                  );
                })}

                {group.options.length === 0 && <p className="choice-options-empty">No hay opciones disponibles en este grupo.</p>}
              </div>

              <p className={`choice-group-status${complete ? ' choice-group-status--complete' : ''}`} id={statusId}>
                <span aria-hidden="true">{complete ? '✓' : '○'}</span>
                {complete ? 'Selección completa' : `Falta seleccionar al menos ${group.min_selections - selected.length}`}
              </p>
            </fieldset>
          );
        })}
      </div>

      <div className={`configuration-summary${configurationReady ? ' configuration-summary--ready' : ''}`} role="status" aria-live="polite">
        <span aria-hidden="true">{configurationReady ? '✓' : '○'}</span>
        <div>
          <strong>{configurationReady ? 'Configuración lista' : 'Completa tus elecciones'}</strong>
          <p>{configurationReady ? 'Tus elecciones están completas para el siguiente paso.' : `Te falta completar ${incompleteGroups.length} ${incompleteGroups.length === 1 ? 'grupo' : 'grupos'}.`}</p>
        </div>
      </div>
    </section>
  );
}
