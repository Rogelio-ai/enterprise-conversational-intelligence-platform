import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProductConfiguration } from '../components/ProductConfiguration';
import type { ChoiceGroupResponse } from '../api/contracts';

function group(overrides: Partial<ChoiceGroupResponse> = {}): ChoiceGroupResponse {
  return {
    id: 10,
    name: 'Bebida',
    min_selections: 1,
    max_selections: 1,
    required: true,
    options: [
      { id: 101, product_id: 201, name: 'Café', description: 'Café de olla', quantity: '1.0000' },
      { id: 102, product_id: 202, name: 'Jugo', description: null, quantity: '1.0000' },
      { id: 103, product_id: 203, name: 'Agua', description: null, quantity: '2.0000' },
    ],
    ...overrides,
  };
}

afterEach(cleanup);

describe('product configuration', () => {
  it('enforces authoritative required single-choice behavior', async () => {
    render(<ProductConfiguration productId={50} groups={[group()]} />);

    expect(screen.getByText('Obligatorio')).toBeInTheDocument();
    expect(screen.getByText('Elige 1 opción')).toBeInTheDocument();
    expect(screen.getByText('1 pendiente')).toBeInTheDocument();
    expect(screen.getByText('Falta seleccionar al menos 1')).toBeInTheDocument();

    const coffee = screen.getByRole('radio', { name: /Café/ });
    const juice = screen.getByRole('radio', { name: /Jugo/ });
    await userEvent.click(coffee);
    expect(coffee).toBeChecked();
    expect(screen.getByText('Configuración lista')).toBeInTheDocument();
    await userEvent.click(juice);
    expect(juice).toBeChecked();
    expect(coffee).not.toBeChecked();
  });

  it('lets an optional single-choice group return to no selection', async () => {
    render(<ProductConfiguration productId={50} groups={[group({ min_selections: 0, required: false })]} />);

    const none = screen.getByRole('radio', { name: /Sin selección/ });
    const coffee = screen.getByRole('radio', { name: /Café/ });
    expect(screen.getByText('Opcional')).toBeInTheDocument();
    expect(screen.getByText('Elige una opción si lo deseas')).toBeInTheDocument();
    expect(none).toBeChecked();
    expect(screen.getByText('Configuración lista')).toBeInTheDocument();

    await userEvent.click(coffee);
    expect(coffee).toBeChecked();
    await userEvent.click(none);
    expect(none).toBeChecked();
    expect(coffee).not.toBeChecked();
  });

  it('enforces multi-choice minimum and maximum limits', async () => {
    render(<ProductConfiguration productId={50} groups={[group({ min_selections: 2, max_selections: 2 })]} />);

    const coffee = screen.getByRole('checkbox', { name: /Café/ });
    const juice = screen.getByRole('checkbox', { name: /Jugo/ });
    const water = screen.getByRole('checkbox', { name: /Agua/ });
    expect(screen.getByText('Elige 2 opciones')).toBeInTheDocument();

    await userEvent.click(coffee);
    expect(screen.getByText('Falta seleccionar al menos 1')).toBeInTheDocument();
    await userEvent.click(juice);
    expect(screen.getByText('Configuración lista')).toBeInTheDocument();
    expect(water).toBeDisabled();

    await userEvent.click(coffee);
    expect(water).toBeEnabled();
    expect(screen.getByText('Completa tus elecciones')).toBeInTheDocument();
  });

  it('supports an explicit minimum-to-maximum range and preserves option details', async () => {
    render(<ProductConfiguration productId={50} groups={[group({ min_selections: 1, max_selections: 2 })]} />);
    expect(screen.getByText('Elige entre 1 y 2 opciones')).toBeInTheDocument();
    expect(screen.getByText('Café de olla')).toBeInTheDocument();
    expect(screen.getByText('Cantidad 2')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox', { name: /Café/ }));
    expect(screen.getByText('Configuración lista')).toBeInTheDocument();
  });

  it('treats an optional multi-choice group as complete with no selection', () => {
    render(<ProductConfiguration productId={50} groups={[group({ min_selections: 0, max_selections: 2, required: false })]} />);
    expect(screen.getByText('Elige hasta 2 opciones')).toBeInTheDocument();
    expect(screen.getByText('Configuración lista')).toBeInTheDocument();
  });

  it('keeps a required group with no authoritative options visibly incomplete', () => {
    render(<ProductConfiguration productId={50} groups={[group({ options: [] })]} />);
    expect(screen.getByText('No hay opciones disponibles en este grupo.')).toBeInTheDocument();
    expect(screen.getByText('Completa tus elecciones')).toBeInTheDocument();
  });
});
