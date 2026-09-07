import { useState, type FormEvent } from 'react';

export interface PaymentCustomerIdentity {
  display_name: string;
  email: string;
  phone: string;
}

interface PaymentContactFormProps {
  initialName: string;
  initialEmail: string;
  onReady: (identity: PaymentCustomerIdentity) => void;
  onEdit: () => void;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_PATTERN = /^\+[0-9]{8,15}$/;

export function PaymentContactForm({ initialName, initialEmail, onReady, onEdit }: PaymentContactFormProps) {
  const [name, setName] = useState(initialName);
  const [email, setEmail] = useState(initialEmail);
  const [phone, setPhone] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const normalizedName = name.trim();
  const normalizedEmail = email.trim().toLocaleLowerCase();
  const normalizedPhone = phone.trim().replace(/[\s().-]+/g, '');
  const errors = {
    name: !normalizedName ? 'Ingresa el nombre para el pago.' : '',
    email: !EMAIL_PATTERN.test(normalizedEmail) ? 'Ingresa un correo electrónico válido.' : '',
    phone: !PHONE_PATTERN.test(normalizedPhone) ? 'Ingresa el teléfono con código de país, por ejemplo +525500000000.' : '',
  };

  function edit(setter: (value: string) => void, value: string) {
    setter(value);
    onEdit();
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (errors.name || errors.email || errors.phone) return;
    onReady({ display_name: normalizedName, email: normalizedEmail, phone: normalizedPhone });
  }

  return (
    <section className="payment-contact" aria-labelledby="payment-contact-title">
      <p className="panel-kicker">Contacto para este pago</p>
      <h2 id="payment-contact-title">Confirma tus datos</h2>
      <p>Estos datos se usan para procesar este pago; no son datos fiscales.</p>
      <form noValidate onSubmit={submit}>
        <label>Nombre<input autoComplete="name" value={name} onChange={(event) => edit(setName, event.target.value)} aria-invalid={submitted && !!errors.name} /></label>
        {submitted && errors.name && <p className="field-error">{errors.name}</p>}
        <label>Correo electrónico<input type="email" autoComplete="email" value={email} onChange={(event) => edit(setEmail, event.target.value)} aria-invalid={submitted && !!errors.email} /></label>
        {submitted && errors.email && <p className="field-error">{errors.email}</p>}
        <label>Teléfono<input type="tel" autoComplete="tel" placeholder="+525500000000" value={phone} onChange={(event) => edit(setPhone, event.target.value)} aria-invalid={submitted && !!errors.phone} /></label>
        {submitted && errors.phone && <p className="field-error">{errors.phone}</p>}
        <button className="primary-button" type="submit">Continuar al formulario de tarjeta</button>
      </form>
    </section>
  );
}
