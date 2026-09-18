<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <http://www.gnu.org/licenses/>.

defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_sparkth';
// Bump whenever db/services.php declarations or lang/ strings change; installed sites
// only pick those up when the version increases.
$plugin->version   = 2026091703;
$plugin->requires  = 2024100700;   // Moodle 4.5 LTS
$plugin->maturity  = MATURITY_ALPHA;
$plugin->release   = '0.1.0';
