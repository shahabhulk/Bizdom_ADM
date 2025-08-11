// /** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";    
publicWidget.registry.AppointForm = publicWidget.Widget.extend({


        selector: '.apoi_form',
      
        events: {
            'click .date-select': '_onSelectDateGet',
            'click .slot_time_select': '_onClickSlotSelect',
            'submit .appoint-submit': '_submitForm',
        },

        init() {
                this._super(...arguments);
                this.orm = this.bindService("orm");
            },
    
        start() {
            const def = this._super(...arguments);
            var today = new Date();
            var dd = String(today.getDate()).padStart(2, '0');
            var mm = String(today.getMonth() + 1).padStart(2, '0');
            var yyyy = today.getFullYear();
            today = yyyy + '-' + mm + '-' + dd;
            $('#appoint_date').attr('min',today);
            return def;
        },
    
        _onSelectDateGet: async function(ev) {

            var weekday = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
            var date = $('input[id="appoint_date"]').val();
            var d = new Date(date);
            var dayName = weekday[d.getDay()];

            const calendar = await this.orm.searchRead('appointement.slots',[],['appointment_date'])                            
            const isDateInCalendar = calendar.map(appointment => appointment.appointment_date).includes(date);
            $('.slot_day').each(function() {
                var weekday_id = $(this).attr('weekday_id')
                if (weekday_id === dayName && isDateInCalendar) {
                    var appointmentDate = $(this).find('h4 span').text();
                    if (appointmentDate === date) {
                        $('.slot').removeClass('d-none')
                        $(this).show();
                        $('input[name="weekday"]').attr('value', dayName);
                    } else {
                        $(this).hide();
                    }
                    
                }
                else{
                    $(this).hide();
                }
            });
        },
    
        _onClickSlotSelect: function(ev) {
            var slot_time = $(ev.currentTarget).attr('slot_time')
            var slot_select = $('input[name="time_slot"]').attr('value', slot_time) 
        },
    
        _submitForm: function(ev) {
            if(!$('input[name="time_slot"]').val()){
                ev.preventDefault();
                $('.time-slot').popover({
                    animation: true,
                    title: _t('DENIED'),
                    container: 'body',
                    trigger: 'focus',
                    placement: 'top',
                    html: true,
                    content: _t('Please Select Slot First'),
                });
                $('.time-slot').popover('show');
            }
        },
    
    });
