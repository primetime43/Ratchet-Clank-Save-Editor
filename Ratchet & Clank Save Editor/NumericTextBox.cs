using System;
using System.ComponentModel;
using System.Drawing;
using System.Globalization;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace primetime43_Ratchet_Clank_Save_Editor
{
    // Plain TextBox with strict parsing; invalid text never falls back to a stale value.
    public sealed class NumericTextBox : TextBox
    {
        private decimal minimum, maximum = int.MaxValue;
        private bool allowDecimal, hexadecimal;
        private string fieldName = "Value";
        private readonly ToolTip validationTip = new();
        public event EventHandler ValueChanged;
        public string ValidationMessage { get; private set; } = string.Empty;
        public bool IsValid => TryGetValue(out _);
        [DefaultValue(typeof(decimal), "0")]
        public decimal Minimum { get => minimum; set { minimum = value; Revalidate(); } }
        [DefaultValue(typeof(decimal), "2147483647")]
        public decimal Maximum { get => maximum; set { maximum = value; Revalidate(); } }
        [DefaultValue(false)]
        public bool AllowDecimal { get => allowDecimal; set { allowDecimal = value; Revalidate(); } }
        [DefaultValue(false)]
        public bool Hexadecimal { get => hexadecimal; set { hexadecimal = value; Revalidate(); } }
        [DefaultValue("Value")]
        public string FieldName { get => fieldName; set { fieldName = value; Revalidate(); } }

        public NumericTextBox()
        {
            MaxLength = 64;
            Text = "0";
        }

        [DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
        public decimal Value
        {
            get => TryGetValue(out decimal value) ? value : throw new InvalidOperationException(ValidationMessage);
            set
            {
                if (value < minimum || value > maximum || (!allowDecimal && value != decimal.Truncate(value)))
                    throw new ArgumentOutOfRangeException(nameof(value));
                Text = hexadecimal ? ((uint)value).ToString("X", CultureInfo.InvariantCulture) :
                    value.ToString("0.############################", CultureInfo.InvariantCulture);
            }
        }

        public bool TryGetValue(out decimal value)
        {
            value = 0;
            string text = Text;
            if (hexadecimal)
            {
                if (text.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) text = text[2..];
                if (!Regex.IsMatch(text, "\\A[0-9A-Fa-f]+\\z") ||
                    !uint.TryParse(text, NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture, out uint bits)) return false;
                value = bits;
            }
            else
            {
                string pattern = allowDecimal ? "\\A(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)\\z" : "\\A[0-9]+\\z";
                if (!Regex.IsMatch(text, pattern) ||
                    !decimal.TryParse(text, allowDecimal ? NumberStyles.AllowDecimalPoint : NumberStyles.None,
                        CultureInfo.InvariantCulture, out value)) return false;
            }
            return value >= minimum && value <= maximum;
        }

        private void Revalidate()
        {
            bool valid = IsValid;
            string syntax = hexadecimal ? "a hexadecimal offset" : allowDecimal ? "a number (use . for decimals)" : "a whole number";
            string lower = hexadecimal ? ((uint)minimum).ToString("X", CultureInfo.InvariantCulture) : minimum.ToString(CultureInfo.InvariantCulture);
            string upper = hexadecimal ? ((uint)maximum).ToString("X", CultureInfo.InvariantCulture) : maximum.ToString(CultureInfo.InvariantCulture);
            ValidationMessage = valid ? string.Empty : $"{fieldName}: enter {syntax} between {lower} and {upper}.";
            BackColor = valid ? SystemColors.Window : AppTheme.InvalidInputBackground;
            AccessibleDescription = ValidationMessage;
            validationTip?.SetToolTip(this, ValidationMessage);
            ValueChanged?.Invoke(this, EventArgs.Empty);
        }

        protected override void OnTextChanged(EventArgs e)
        {
            base.OnTextChanged(e);
            Revalidate();
        }

        protected override void OnKeyPress(KeyPressEventArgs e)
        {
            if (!char.IsControl(e.KeyChar))
            {
                bool digit = e.KeyChar is >= '0' and <= '9';
                bool hex = hexadecimal && (e.KeyChar is >= 'a' and <= 'f' or >= 'A' and <= 'F' or 'x' or 'X');
                bool point = !hexadecimal && allowDecimal && e.KeyChar == '.' &&
                    !Text.Remove(SelectionStart, SelectionLength).Contains('.');
                if (!digit && !hex && !point) e.Handled = true;
            }
            base.OnKeyPress(e);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) validationTip.Dispose();
            base.Dispose(disposing);
        }
    }
}
